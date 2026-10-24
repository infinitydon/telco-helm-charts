package main

import (
	"github.com/ellanetworks/core/internal/tester/logger"
	phones "github.com/ellanetworks/core/internal/tester/scenarios/gnb"
	"go.uber.org/zap/zapcore"
	"log"
	"os"
)

func main() {
	logger.Init(zapcore.InfoLevel)
	if err := phones.ServePhones(os.Getenv("HTTP_ADDRESS")); err != nil {
		log.Fatal(err)
	}
}
