class APPlayerController extends DunDefPlayerController;

// Steam remains available for native DLC ownership queries, not invitations.
// This also covers callbacks registered before the viewport's next tick.
function OnGameInviteAccepted(const out OnlineGameSearchResult InviteResult)
{
}
