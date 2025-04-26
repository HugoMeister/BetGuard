// GoBackend/main.go

package main

import (
	"bytes"
	"encoding/json"
	"io/ioutil"
	"log"
	"math"
	"net/http"

	"github.com/gin-gonic/gin"
)

type MatchFeatures struct {
	HomeAvgGoals float64 `json:"home_avg_goals"`
	AwayAvgGoals float64 `json:"away_avg_goals"`
	HomeForm     int     `json:"home_form"`
	AwayForm     int     `json:"away_form"`
}

type PredictResponse struct {
	HomeWinProbability    float64 `json:"home_win_probability"`
	AwayOrDrawProbability float64 `json:"away_or_draw_probability"`
}

type Match struct {
	HomeTeam string
	AwayTeam string
	HomeOdds float64
	DrawOdds float64
	AwayOdds float64
}

type Alert struct {
	Match              string  `json:"match"`
	BetType            string  `json:"bet_type"`
	ModelProbability   float64 `json:"model_probability"`
	ImpliedProbability float64 `json:"implied_probability"`
	Delta              float64 `json:"delta"`
	Alert              bool    `json:"alert"`
}

func main() {
	router := gin.Default()

	router.GET("/recommendations", func(c *gin.Context) {
		alerts := generateRecommendations()
		c.JSON(200, alerts)
	})

	router.Run(":8080") // Go backend będzie na localhost:8080
}

func generateRecommendations() []Alert {
	// Lista meczów (na start hardkodowana, potem dynamicznie)
	matches := []Match{
		{
			HomeTeam: "Arsenal",
			AwayTeam: "Chelsea",
			HomeOdds: 2.0,
			DrawOdds: 3.5,
			AwayOdds: 3.8,
		},
		{
			HomeTeam: "Manchester United",
			AwayTeam: "Liverpool",
			HomeOdds: 2.5,
			DrawOdds: 3.2,
			AwayOdds: 2.9,
		},
	}

	var alerts []Alert

	for _, match := range matches {
		features := MatchFeatures{
			HomeAvgGoals: 1.8,
			AwayAvgGoals: 1.2,
			HomeForm:     12,
			AwayForm:     6,
		}

		modelProba := callMlService(features)

		impliedHomeProba := 1.0 / match.HomeOdds
		delta := modelProba.HomeWinProbability - impliedHomeProba

		alert := Alert{
			Match:              match.HomeTeam + " vs " + match.AwayTeam,
			BetType:            "Home Win",
			ModelProbability:   round(modelProba.HomeWinProbability*100, 2),
			ImpliedProbability: round(impliedHomeProba*100, 2),
			Delta:              round(delta*100, 2),
			Alert:              delta > 0.1, // 10% różnicy
		}

		alerts = append(alerts, alert)
	}

	return alerts
}

func callMlService(features MatchFeatures) PredictResponse {
	url := "http://ml-service:8000/predict"

	jsonData, err := json.Marshal(features)
	if err != nil {
		log.Fatal(err)
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Fatal(err)
	}
	defer resp.Body.Close()

	body, _ := ioutil.ReadAll(resp.Body)

	var predict PredictResponse
	json.Unmarshal(body, &predict)

	return predict
}

func round(x float64, precision int) float64 {
	pow := math.Pow(10, float64(precision))
	return math.Round(x*pow) / pow
}
