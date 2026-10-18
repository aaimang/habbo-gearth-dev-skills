const MAX_CLUB_FURNI_ID = 0x7FFFFFFF;
const MIN_CLUB_FURNI_ID = MAX_CLUB_FURNI_ID - 0xFFFF;

function toFurniId(gameFurniId: number): FurniIdValue {
  const isWall = gameFurniId < 0;
  const normalized = isWall ? gameFurniId * -1 : gameFurniId;

  if (normalized >= MIN_CLUB_FURNI_ID) {
    const id = normalized - MIN_CLUB_FURNI_ID;
    return isWall ? FurniId.bcWallItem(id) : FurniId.bcFurni(id);
  }

  return isWall ? FurniId.wallItem(normalized) : FurniId.furni(normalized);
}

function fromFurniId(furniId: FurniIdValue): number {
  const localId = furniId.id;
  const baseId = furniId.kind === "furni-bc" || furniId.kind === "wall-items-bc"
    ? localId + MIN_CLUB_FURNI_ID
    : localId;

  return furniId.kind === "wall-items" || furniId.kind === "wall-items-bc"
    ? baseId * -1
    : baseId;
}