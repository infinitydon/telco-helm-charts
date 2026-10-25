package gnb

import (
	"github.com/ellanetworks/core/internal/tester/ue"
	"time"
)

// DashboardInternetSession returns the already-established internet PDU session.
func (g *GnodeB) DashboardInternetSession(u *ue.UE, ranID int64) (PDUSessionResult, error) {
	return g.awaitSession(u, ranID, 1, 0, 5*time.Second)
}
