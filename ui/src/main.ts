import './style.css';
import { InMemoryDesktopBridge, WebViewDesktopBridge } from './bridge';
import { DesktopAppController } from './people_controller';
import { runPeopleRosterRegressionSuite } from './roster_suite';

const root = document.querySelector<HTMLDivElement>('#app');
if (root) {
  const params = new URLSearchParams(typeof location !== 'undefined' ? location.search : '');
  if (params.get('suite') === 'roster500') {
    void runPeopleRosterRegressionSuite(root).then((result) => {
      window.chrome?.webview?.postMessage({
        kind: 'suite_result',
        result,
      });
    });
  } else {
    const hasWebViewHost = typeof window !== 'undefined' && Boolean(window.chrome?.webview);
    const bridge = hasWebViewHost
      ? new WebViewDesktopBridge()
      : new InMemoryDesktopBridge({
          revision: 1,
          session: 'standalone-preview-session',
          players: [
            {
              id: 'self-pilot',
              handle: 'YourPilot',
              tags: ['Org'],
              is_self: true,
              is_org: true,
              in_party: true,
              is_friend: true,
              on_shard: true,
              relationship: 'You',
            },
            {
              id: 'party-pilot',
              handle: 'Cassiopeia',
              tags: ['Crew', 'Friendly'],
              in_party: true,
              is_friend: true,
              on_shard: true,
              relationship: 'Party + Friend',
            },
            {
              id: 'friend-pilot',
              handle: 'NovaDrift',
              tags: ['Trader', 'Friend'],
              is_friend: true,
              on_shard: true,
              relationship: 'Friend',
              requests: {
                friend: { outcome: 'Sent', detail: 'Friend request receipt returned' },
              },
            },
            {
              id: 'org-pilot',
              handle: 'OrionAtlas',
              tags: ['Org Affiliate'],
              is_org: true,
              on_shard: true,
              relationship: 'Org',
            },
          ],
          action_people: [],
          friends_known: true,
          party_known: true,
          status: 'Standalone preview — no live game connection',
        });

    const controller = new DesktopAppController(root, bridge);
    (window as unknown as Record<string, unknown>).__synthscanDesktop = {
      controller,
      bridge,
    };
  }
}
