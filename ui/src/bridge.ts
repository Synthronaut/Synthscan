/** Proposed boundary only. No production adapter or game actions are connected. */
export interface Player { id: string; handle: string; tags: string[]; }
export interface PeopleSnapshot { revision: number; session: string; players: Player[]; }
export interface DesktopBridge {
  subscribePeople(listener: (snapshot: PeopleSnapshot) => void): () => void;
  stagePlayers(ids: string[]): Promise<void>;
}
export const ACTION_LIMIT = 50;
