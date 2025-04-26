# Build stage
FROM golang:1.24 AS builder

WORKDIR /app

COPY go.mod ./
COPY go.sum ./
RUN go mod download

COPY . .

RUN go build -o main .

# Run stage
FROM golang:1.24

WORKDIR /app

COPY --from=builder /app/main .

EXPOSE 8080

CMD ["./main"]
