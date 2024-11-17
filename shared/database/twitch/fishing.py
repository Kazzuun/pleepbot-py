from asyncpg import Pool, Record

from .models import Fisher, FishingEquipment


class FishingEquipmentCatalogue:
    def __init__(self) -> None:
        self._equipment = [
            FishingEquipment(
                id=11,
                name="fishing net",
                cost=30,
                level_req=3,
                effect=1,
                effect_disc="+1 fish",
                equipment_type="FISHFLAT",
            ),
            FishingEquipment(
                id=12,
                name="fishing radar",
                cost=100,
                level_req=5,
                effect=0.1,
                effect_disc="+10% fish",
                equipment_type="FISHMULTI",
            ),
            FishingEquipment(
                id=1,
                name="fishing socks",
                cost=500,
                level_req=10,
                effect=0.15,
                effect_disc="+15% exp",
                equipment_type="EXPMULTI",
            ),
            FishingEquipment(
                id=2,
                name="canned worms",
                cost=1000,
                level_req=15,
                effect=1,
                effect_disc="+1 fish",
                equipment_type="FISHFLAT",
            ),
            FishingEquipment(
                id=3,
                name="fishing rod holder",
                cost=3000,
                level_req=20,
                effect=1.0,
                effect_disc="+100% afk fishing",
                equipment_type="AFKMULTI",
            ),
            FishingEquipment(
                id=13,
                name="silver lures",
                cost=5000,
                level_req=20,
                effect=0.05,
                effect_disc="+5% haul chance",
                equipment_type="HAULCHANCE",
            ),
            FishingEquipment(
                id=4,
                name="carbon fiber fishing line",
                cost=5000,
                level_req=25,
                effect=None,
                effect_disc="roll rng twice and get max",
                equipment_type="LESSRNG",
            ),
            FishingEquipment(
                id=5,
                name="alarm clock",
                cost=6000,
                level_req=25,
                effect=1800,
                effect_disc="-30 min cooldown",
                equipment_type="COOLDOWNFLAT",
            ),
            FishingEquipment(
                id=6,
                name="exquisite fish food",
                cost=10000,
                level_req=30,
                effect=3,
                effect_disc="+3 fish",
                equipment_type="FISHFLAT",
            ),
            FishingEquipment(
                id=7,
                name="cool fishing hat",
                cost=10000,
                level_req=30,
                effect=0.35,
                effect_disc="+35% exp",
                equipment_type="EXPMULTI",
            ),
            FishingEquipment(
                id=14,
                name="fishing trawler",
                cost=10000,
                level_req=35,
                effect=0.1,
                effect_disc="+10% haul chance",
                equipment_type="HAULCHANCE",
            ),
            FishingEquipment(
                id=8,
                name="a dog",
                cost=10000,
                level_req=40,
                effect=1800,
                effect_disc="-30 min cooldown",
                equipment_type="COOLDOWNFLAT",
            ),
            FishingEquipment(
                id=9,
                name="deep sea fishing boat",
                cost=20000,
                level_req=40,
                effect=0.25,
                effect_disc="+25% fish",
                equipment_type="FISHMULTI",
            ),
            FishingEquipment(
                id=15,
                name="golden fishing trawler",
                cost=15000,
                level_req=45,
                effect=0.1,
                effect_disc="+10% haul chance",
                equipment_type="HAULCHANCE",
            ),
            FishingEquipment(
                id=16,
                name="unbreakable fishing line",
                cost=20000,
                level_req=45,
                effect=None,
                effect_disc="max number of fish every time",
                equipment_type="NORNG",
            ),
            FishingEquipment(
                id=10,
                name="a cat",
                cost=15000,
                level_req=50,
                effect=1800,
                effect_disc="-30 min cooldown",
                equipment_type="COOLDOWNFLAT",
            ),
            FishingEquipment(
                id=17,
                name="yacht",
                cost=20000,
                level_req=50,
                effect=0.5,
                effect_disc="+50% haul size",
                equipment_type="HAULSIZEMULTI",
            ),
        ]

    def item_by_id(self, id: int) -> FishingEquipment | None:
        target_item = [item for item in self._equipment if item.id == id]
        if len(target_item) > 0:
            return target_item[0]

    def equipment_owned(self, owned_equipment_num: int) -> list[FishingEquipment]:
        owned = []
        for item in self._equipment:
            if owned_equipment_num & (1 << (item.id - 1)) != 0:
                owned.append(item)
        return owned

    def equipment_not_owned(self, owned_equipment_num: int) -> list[FishingEquipment]:
        not_owned = []
        for item in self._equipment:
            if owned_equipment_num & (1 << (item.id - 1)) == 0:
                not_owned.append(item)
        return not_owned

    def all_equipment(self) -> list[FishingEquipment]:
        return self._equipment


async def fish(pool: Pool, user_id: str, fish_count: int, exp_amount: int) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.old_fish (user_id, fish_count, exp, last_fished)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    fish_count = twitch.old_fish.fish_count + EXCLUDED.fish_count,
                    exp = twitch.old_fish.exp + EXCLUDED.exp,
                    last_fished = CURRENT_TIMESTAMP
                """,
                user_id,
                fish_count,
                exp_amount,
            )


async def fisher(pool: Pool, user_id: str) -> Fisher:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT user_id, fish_count, exp, last_fished, equipment
                FROM twitch.old_fish
                WHERE user_id = $1;
                """,
                user_id,
            )
            if result is None:
                return Fisher(user_id=user_id)
            return Fisher(**result)


async def top_exp(pool: Pool) -> list[Fisher]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT user_id, fish_count, exp, last_fished, equipment
                FROM twitch.old_fish
                ORDER BY exp DESC;
                """
            )
            return [Fisher(**result) for result in results]


async def buy_fishing_equipment(pool: Pool, user_id: str, equipment_id: int, cost: int) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.old_fish
                SET exp = exp - $2, equipment = equipment + $3
                WHERE user_id = $1;
                """,
                user_id,
                cost,
                1 << (equipment_id - 1),
            )
