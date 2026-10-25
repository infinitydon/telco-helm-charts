package gnb

import (
	"fmt"
	radio "github.com/ellanetworks/core/internal/tester/gnb"
	"github.com/ellanetworks/core/internal/tester/scenarios"
	"os"
)

func phoneMode() string {
	if m := os.Getenv("UE_MODE"); m != "" {
		return m
	}
	return "internet-ims-sms"
}
func servicesEnabled() bool { return phoneMode() == "internet-ims-sms" }

// Internet-only registration creates the default PDU session without SMS capability,
// an IMS PDU session, P-CSCF discovery, SIP, or kernel IPsec resources.
func attachInternetUEs(env scenarios.Env, g *radio.GnodeB, subs ...scenarios.SubscriberSpec) ([]scenarios.IMSEndpoint, []imsCallUE, error) {
	var endpoints []scenarios.IMSEndpoint
	var ues []imsCallUE
	for i, s := range subs {
		sub := subscriber{IMSI: s.IMSI, Key: s.Key, OPc: s.OPc, SequenceNumber: s.SequenceNumber, ProfileName: s.ProfileName}
		u, err := newSubscriberUE(g, sub, scenarios.DefaultDNN, env.PDUSessionType())
		if err != nil {
			return nil, nil, err
		}
		id := int64(scenarios.DefaultRANUENGAPID + i)
		g.AddUE(id, u)
		registration, err := g.Register(u, id, scenarios.DefaultPDUSessionID, registrationTimeout)
		if err != nil {
			return nil, nil, fmt.Errorf("internet registration: %w", err)
		}
		endpoints = append(endpoints, scenarios.IMSEndpoint{Subscriber: s})
		ues = append(ues, imsCallUE{ue: u, leg: voiceLeg{gnb: g, ranUEID: id, session: registration.Session}})
	}
	return endpoints, ues, nil
}
