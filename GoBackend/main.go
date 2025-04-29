package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"net/http"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/gin-gonic/gin"
	"golang.org/x/text/unicode/norm"
)

const (
	footballDataToken = "4ee1ff5f5ef14e338e79648b2ae106d9"
	oddsAPIKey        = "6ae063796adc45e431a0e1644ca15162"
	minDelta          = 0.08 // Minimalna różnica (%) dla valuebetu
)

var (
	// lista lig do pobierania kursów
	leagues = []string{
		"soccer_epl",
		"soccer_spain_la_liga",
	}

	// cache i mapy pomocnicze
	teamIDs             = map[string]int{}    // canonical name → ID
	aliasToCanonical    = map[string]string{} // normalized key → canonical name
	recentMatchesCache  = make(map[string][]HistoricalMatch)
	cacheMutex          = sync.RWMutex{}
)

type HistoricalMatch struct {
	Date      time.Time
	HomeTeam  string
	AwayTeam  string
	HomeScore int
	AwayScore int
}

type MatchFeatures struct {
    League       string  `json:"league"`
    Season       string  `json:"season"`
    HomeAvgGoals float64 `json:"home_avg_goals"`
    AwayAvgGoals float64 `json:"away_avg_goals"`
    HomeForm     int     `json:"home_form"`
    AwayForm     int     `json:"away_form"`
    B365H        float64 `json:"b365h"`
    B365D        float64 `json:"b365d"`
    B365A        float64 `json:"b365a"`
}

type PredictResponse struct {
	HomeWinProbability float64 `json:"home_win_probability"`
	DrawProbability    float64 `json:"draw_probability"`
	AwayWinProbability float64 `json:"away_win_probability"`
}

type Match struct {
    HomeTeam string
    AwayTeam string
    HomeOdds float64
    DrawOdds float64
    AwayOdds float64
    SportKey string // klucz ligi, np. "soccer_epl"
}

type Alert struct {
	Match              string  `json:"match"`
	BetType            string  `json:"bet_type"`
	ModelProbability   float64 `json:"model_probability"`
	ImpliedProbability float64 `json:"implied_probability"`
	Delta              float64 `json:"delta"`
	Alert              bool    `json:"alert"`
}


var (
    // cachedAlerts holds the last computation of generateRecommendations()
    cachedAlerts []Alert
    alertsMu     sync.RWMutex
)

func main() {
    // 1) Load team IDs once at startup
    loadTeamIDsFromAPI()

    // 2) Kick off a background refresher
    go func() {
        // do it immediately
        refreshAlerts()
        ticker := time.NewTicker(1 * time.Minute)
        defer ticker.Stop()
        for range ticker.C {
            refreshAlerts()
        }
    }()

    // 3) Expose a super‐light handler
    router := gin.Default()
    router.GET("/recommendations", func(c *gin.Context) {
        alertsMu.RLock()
        result := cachedAlerts
        alertsMu.RUnlock()
        c.JSON(http.StatusOK, result)
    })
    router.Run(":8080")
}

// refreshAlerts recomputes generateRecommendations() and swaps it in atomically.
func refreshAlerts() {
    log.Println("🔄 Refreshing alerts…")
    newAlerts := generateRecommendations()
    alertsMu.Lock()
    cachedAlerts = newAlerts
    alertsMu.Unlock()
    log.Printf("✅ Refreshed: %d alerts cached\n", len(newAlerts))
}

// generateRecommendations fetches odds, preloads each team’s recent matches in parallel,
// then evaluates every match using the cached data for maximum speed.
func generateRecommendations() []Alert {
    var alerts []Alert

    // 1) Gather all upcoming matches from each league
    var allMatches []Match
    for _, league := range leagues {
        allMatches = append(allMatches, fetchMatchesFromOddsAPI(league)...)
    }

    // 2) Build a set of unique team names
    teamSet := make(map[string]struct{}, len(allMatches)*2)
    for _, m := range allMatches {
        teamSet[m.HomeTeam] = struct{}{}
        teamSet[m.AwayTeam] = struct{}{}
    }

    // 3) Prefetch each team’s last 10 matches in parallel (populates recentMatchesCache)
    var wg sync.WaitGroup
    for team := range teamSet {
        wg.Add(1)
        go func(tm string) {
            defer wg.Done()
            fetchRecentMatches(tm, 10)
        }(team)
    }
    wg.Wait()

    // 4) Now evaluate each match (uses the cached historical data)
    for _, m := range allMatches {
        alerts = append(alerts, evaluateMatch(m)...)
    }

    return alerts
}

func fetchMatchesFromOddsAPI(sportKey string) []Match {
	url := fmt.Sprintf(
		"https://api.the-odds-api.com/v4/sports/%s/odds?regions=eu&markets=h2h&apiKey=%s",
		sportKey, oddsAPIKey,
	)

	resp, err := http.Get(url)
	if err != nil {
		log.Printf("❌ Error fetching odds for %s: %v", sportKey, err)
		return nil
	}
	defer resp.Body.Close()

	body, _ := ioutil.ReadAll(resp.Body)

	// Spróbuj zdekodować do tablicy
	var arr []struct {
		HomeTeam   string `json:"home_team"`
		AwayTeam   string `json:"away_team"`
		Bookmakers []struct {
			Markets []struct {
				Outcomes []struct {
					Name  string  `json:"name"`
					Price float64 `json:"price"`
				} `json:"outcomes"`
			} `json:"markets"`
		} `json:"bookmakers"`
	}

	if err := json.Unmarshal(body, &arr); err != nil {
		var obj map[string]interface{}
		if err2 := json.Unmarshal(body, &obj); err2 == nil {
			log.Printf("❌ Odds API zwróciło obiekt zamiast tablicy: %v", obj)
		} else {
			log.Printf("❌ Error parsing odds API response: %v", err)
		}
		return nil
	}

	var matches []Match
	for _, e := range arr {
		if len(e.Bookmakers) == 0 || len(e.Bookmakers[0].Markets) == 0 {
			continue
		}
		var h, d, a float64
		for _, o := range e.Bookmakers[0].Markets[0].Outcomes {
			switch o.Name {
			case e.HomeTeam:
				h = o.Price
			case e.AwayTeam:
				a = o.Price
			case "Draw":
				d = o.Price
			}
		}
		if h > 0 && a > 0 {
			matches = append(matches, Match{
				HomeTeam: e.HomeTeam,
				AwayTeam: e.AwayTeam,
				HomeOdds: h,
				DrawOdds: d,
				AwayOdds: a,
			})
		}
	}
	return matches
}

func evaluateMatch(m Match) []Alert {
    // 1) Wygeneruj cechy historyczne
    base := generateFeatures(m.HomeTeam, m.AwayTeam)

    // 2) Zmapuj SportKey -> kod ligi w modelu i ustaw sezon
    leagueMap := map[string]string{
        "soccer_epl":           "E0",
        "soccer_spain_la_liga": "SP1",
    }
    features := MatchFeatures{
        League:       leagueMap[m.SportKey],
        Season:       "2425", // lub inny aktualny kod sezonu
        HomeAvgGoals: base.HomeAvgGoals,
        AwayAvgGoals: base.AwayAvgGoals,
        HomeForm:     base.HomeForm,
        AwayForm:     base.AwayForm,
        B365H:        m.HomeOdds,
        B365D:        m.DrawOdds,
        B365A:        m.AwayOdds,
    }

    // 3) Wywołanie ML-serwisu
    pr := callMlService(features)

    // 4) Oblicz implied probabilities
    impH := 1.0 / m.HomeOdds
    impD := 1.0 / m.DrawOdds
    impA := 1.0 / m.AwayOdds

    // 5) Zbierz alerty
    var alerts []Alert
    add := func(betType string, modelP, impliedP float64) {
        delta := modelP - impliedP
        alerts = append(alerts, Alert{
            Match:              m.HomeTeam + " vs " + m.AwayTeam,
            BetType:            betType,
            ModelProbability:   round(modelP*100, 2),
            ImpliedProbability: round(impliedP*100, 2),
            Delta:              round(delta*100, 2),
            Alert:              delta > minDelta,
        })
    }
    add("Home Win", pr.HomeWinProbability, impH)
    add("Draw",     pr.DrawProbability,     impD)
    add("Away Win", pr.AwayWinProbability,  impA)

    return alerts
}

func callMlService(features MatchFeatures) PredictResponse {
	url := "http://ml-service:8000/predict"
	jsonData, _ := json.Marshal(features)

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Fatal(err)
	}
	defer resp.Body.Close()

	var pr PredictResponse
	if err := json.NewDecoder(resp.Body).Decode(&pr); err != nil {
		log.Printf("❌ Błąd parsowania JSON: %v", err)
	}
	return pr
}

func generateFeatures(home, away string) MatchFeatures {
	home = getCanonicalName(home)
	away = getCanonicalName(away)

	homeMatches := fetchRecentMatches(home, 10)
	awayMatches := fetchRecentMatches(away, 10)
	now := time.Now()

	return MatchFeatures{
		HomeAvgGoals: round(calculateAvgGoals(homeMatches, home, now, true, 5), 2),
		AwayAvgGoals: round(calculateAvgGoals(awayMatches, away, now, false, 5), 2),
		HomeForm:     calculateForm(homeMatches, home, now, 5),
		AwayForm:     calculateForm(awayMatches, away, now, 5),
	}
}

func fetchRecentMatches(teamName string, maxMatches int) []HistoricalMatch {
	cacheMutex.RLock()
	if m, ok := recentMatchesCache[teamName]; ok {
		cacheMutex.RUnlock()
		return m
	}
	cacheMutex.RUnlock()

	teamID, ok := findTeamID(teamName)
	if !ok {
		log.Printf("⚠️ Nie znaleziono ID dla drużyny: %s", teamName)
		return nil
	}

	url := fmt.Sprintf(
		"https://api.football-data.org/v4/teams/%d/matches?status=FINISHED&limit=%d",
		teamID, maxMatches,
	)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("X-Auth-Token", footballDataToken)

	var data struct {
		Matches []struct {
			UtcDate string `json:"utcDate"`
			Home    struct{ Name string `json:"name"` } `json:"homeTeam"`
			Away    struct{ Name string `json:"name"` } `json:"awayTeam"`
			Score   struct {
				FullTime struct {
					Home int `json:"home"`
					Away int `json:"away"`
				} `json:"fullTime"`
			} `json:"score"`
		} `json:"matches"`
	}

	for {
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			log.Printf("❌ Błąd zapytania do Football-Data: %v", err)
			return nil
		}
		defer resp.Body.Close()

		if resp.StatusCode == http.StatusTooManyRequests {
			log.Printf("⚠️ Rate limit dla %s – śpię 60s i próbuję ponownie...", teamName)
			time.Sleep(time.Minute)
			continue
		}
		if resp.StatusCode != http.StatusOK {
			log.Printf("❌ Football-Data zwrócił status %d dla %s", resp.StatusCode, url)
			return nil
		}

		if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
			log.Printf("❌ Błąd dekodowania JSON: %v", err)
			return nil
		}
		break
	}

	var matches []HistoricalMatch
	for _, m := range data.Matches {
		date, _ := time.Parse(time.RFC3339, m.UtcDate)
		matches = append(matches, HistoricalMatch{
			Date:      date,
			HomeTeam:  m.Home.Name,
			AwayTeam:  m.Away.Name,
			HomeScore: m.Score.FullTime.Home,
			AwayScore: m.Score.FullTime.Away,
		})
	}

	cacheMutex.Lock()
	recentMatchesCache[teamName] = matches
	cacheMutex.Unlock()

	log.Printf("⚙️ %s – znaleziono %d zakończonych meczów", teamName, len(matches))
	return matches
}

func normalizeKey(s string) string {
	s = strings.ToLower(s)
	s = norm.NFD.String(s)
	var b1 strings.Builder
	for _, r := range s {
		if unicode.Is(unicode.Mn, r) {
			continue
		}
		b1.WriteRune(r)
	}
	s = b1.String()

	s = strings.ReplaceAll(s, "&", "and")
	s = strings.TrimPrefix(s, "afc ")
	s = strings.TrimSuffix(s, " fc")

	var b2 strings.Builder
	for _, r := range s {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			b2.WriteRune(r)
		}
	}
	return b2.String()
}

func getCanonicalName(name string) string {
	key := normalizeKey(name)
	if canon, ok := aliasToCanonical[key]; ok {
		return canon
	}
	return name
}

func loadTeamIDsFromAPI() {
	competitions := []int{2021, 2014}
	ignore := map[string]bool{"fc": true, "cf": true, "rc": true, "rcd": true, "ud": true, "ca": true, "cd": true, "club": true, "de": true}

	for _, compID := range competitions {
		url := fmt.Sprintf("https://api.football-data.org/v4/competitions/%d/teams", compID)
		req, _ := http.NewRequest("GET", url, nil)
		req.Header.Set("X-Auth-Token", footballDataToken)
		resp, err := http.DefaultClient.Do(req)
		if err != nil || resp.StatusCode != http.StatusOK {
			log.Printf("❌ Błąd fetch teams %d: %v (status %d)", compID, err, resp.StatusCode)
			continue
		}
		var data struct {
			Teams []struct {
				ID   int    `json:"id"`
				Name string `json:"name"`
			} `json:"teams"`
		}
		json.NewDecoder(resp.Body).Decode(&data)
		resp.Body.Close()

		for _, t := range data.Teams {
			teamIDs[t.Name] = t.ID
			baseKey := normalizeKey(t.Name)
			aliasToCanonical[baseKey] = t.Name

			words := strings.Fields(t.Name)
			var filtered []string
			for _, w := range words {
				if !ignore[strings.ToLower(w)] {
					filtered = append(filtered, w)
				}
			}
			for i := 1; i <= len(filtered); i++ {
				aliasToCanonical[normalizeKey(strings.Join(filtered[:i], " "))] = t.Name
			}
		}
	}
}

func findTeamID(name string) (int, bool) {
	key := normalizeKey(name)
	if canon, ok := aliasToCanonical[key]; ok {
		return teamIDs[canon], true
	}
	for k, canon := range aliasToCanonical {
		if strings.HasPrefix(key, k) || strings.HasSuffix(k, key) {
			return teamIDs[canon], true
		}
	}
	return 0, false
}

func getResult(m HistoricalMatch) string {
	if m.HomeScore > m.AwayScore {
		return "H"
	} else if m.HomeScore < m.AwayScore {
		return "A"
	}
	return "D"
}

func calculateForm(matches []HistoricalMatch, team string, date time.Time, N int) int {
	count, score := 0, 0
	for i := len(matches) - 1; i >= 0 && count < N; i-- {
		m := matches[i]
		if m.Date.After(date) {
			continue
		}
		if m.HomeTeam != team && m.AwayTeam != team {
			continue
		}
		res := getResult(m)
		if m.HomeTeam == team && (res == "H" || res == "D") {
			if res == "H" {
				score += 3
			} else {
				score++
			}
		}
		if m.AwayTeam == team && (res == "A" || res == "D") {
			if res == "A" {
				score += 3
			} else {
				score++
			}
		}
		count++
	}
	return score
}

func calculateAvgGoals(matches []HistoricalMatch, team string, date time.Time, home bool, N int) float64 {
	count, total := 0, 0.0
	for i := len(matches) - 1; i >= 0 && count < N; i-- {
		m := matches[i]
		if m.Date.After(date) {
			continue
		}
		if home && m.HomeTeam == team {
			total += float64(m.HomeScore)
			count++
		}
		if !home && m.AwayTeam == team {
			total += float64(m.AwayScore)
			count++
		}
	}
	if count == 0 {
		return 0
	}
	return total / float64(count)
}

func round(x float64, prec int) float64 {
	return math.Round(x*math.Pow(10, float64(prec))) / math.Pow(10, float64(prec))
}
