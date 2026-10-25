package gnb

import (
	"encoding/json"
	"fmt"
	radio "github.com/ellanetworks/core/internal/tester/gnb"
	"github.com/ellanetworks/core/internal/tester/scenarios"
	"github.com/ellanetworks/core/ngap"
	"net/http"
	"os"
	"time"
)

func phoneIDs() string {
	if os.Getenv("PHONE_ID") == "1" {
		return "['1']"
	}
	if os.Getenv("PHONE_ID") == "2" {
		return "['2']"
	}
	return "['1','2']"
}
func startPhoneGNB(env scenarios.Env) (*radio.GnodeB, error) {
	id := os.Getenv("GNB_ID")
	if id == "" {
		return startGNB(env)
	}
	g := env.FirstGNB()
	node, err := radio.Start(&radio.StartOpts{GnbID: id, MCC: scenarios.DefaultMCC, MNC: scenarios.DefaultMNC, SST: scenarios.DefaultSST, SD: scenarios.DefaultSD, DNN: scenarios.DefaultDNN, TAC: scenarios.DefaultTAC, Name: "Ella-Phone-" + os.Getenv("PHONE_ID"), CoreN2Addresses: env.CoreN2Addresses, GnbN2Address: g.N2Address, GnbN3Address: g.N3Address})
	if err != nil {
		return nil, err
	}
	if _, err = node.WaitForMessage(radio.Successful, ngap.ProcNGSetup, scenarios.NGSetupTimeout); err != nil {
		node.Close()
		return nil, fmt.Errorf("NG setup: %w", err)
	}
	return node, nil
}

// Delivery status comes from the other UE receiving the real NAS message.
func (d *phoneDashboard) trackDelivery(p *dashboardPhone, id uint64, text, to string) {
	client := &http.Client{Timeout: 2 * time.Second}
	for attempt := 0; attempt < 30; attempt++ {
		time.Sleep(time.Second)
		response, err := client.Get(os.Getenv("PEER_URL") + "/api/state")
		if err != nil {
			continue
		}
		var state struct {
			Phones []struct {
				Number   string
				Messages []phoneMessage
			}
		}
		err = json.NewDecoder(response.Body).Decode(&state)
		response.Body.Close()
		if err != nil {
			continue
		}
		p.mu.Lock()
		var sent *phoneMessage
		for i := range p.messages {
			if p.messages[i].ID == id {
				sent = &p.messages[i]
				break
			}
		}
		if sent == nil {
			p.mu.Unlock()
			return
		}
		delivered := false
		for _, peer := range state.Phones {
			if peer.Number != to {
				continue
			}
			for _, m := range peer.Messages {
				if m.Direction == "received" && m.Peer == p.endpoint.Subscriber.MSISDN && m.Text == text && !m.At.Before(sent.At) {
					delivered = true
				}
			}
		}
		if delivered {
			sent.Status = "delivered to UE"
		}
		p.mu.Unlock()
		if delivered {
			return
		}
	}
}
