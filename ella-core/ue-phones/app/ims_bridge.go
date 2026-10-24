package scenarios

import (
	"github.com/ellanetworks/ims/sip"
	"github.com/ellanetworks/ims/testue"
)

// DashboardIMS keeps the upstream UE and its kernel IPsec resources alive.
func DashboardIMS(endpoint IMSEndpoint) (*testue.UE, func(), error) {
	u, err := newIMSUE(endpoint.Subscriber, endpoint.PCSCF, endpoint.Local, sip.UDP, 0)
	if err != nil {
		return nil, nil, err
	}
	return u.UE, u.close, nil
}
