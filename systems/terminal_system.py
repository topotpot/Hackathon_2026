

SECTIONS = ["SURVIVAL", "BIOMES", "TOWERS", "STORMS", "HISTORY", "LOGS", "SETTINGS"]

ENTRIES = [
    {"id": "SOP-001", "section": "SURVIVAL", "unlock": "always"},
    {"id": "SOP-002", "section": "SURVIVAL", "unlock": "always"},
    {"id": "SOP-003", "section": "SURVIVAL", "unlock": "always"},
    {"id": "SOP-004", "section": "SURVIVAL", "unlock": {"towers": 1}},
    {"id": "SOP-005", "section": "SURVIVAL", "unlock": {"level": 1}},
    {"id": "SOP-006", "section": "SURVIVAL", "unlock": {"towers": 1}},
    {"id": "SOP-007", "section": "SURVIVAL", "unlock": {"storms": 1}},
    {"id": "BIO-001", "section": "BIOMES", "unlock": "always"},
    {"id": "BIO-002", "section": "BIOMES", "unlock": {"biome": "ROCKS"}},
    {"id": "BIO-003", "section": "BIOMES", "unlock": {"biome": "MAGNETIC"}},
    {"id": "BIO-004", "section": "BIOMES", "unlock": {"biome": "SHADOW"}},
    {"id": "TWR-001", "section": "TOWERS", "unlock": "always"},
    {"id": "TWR-002", "section": "TOWERS", "unlock": "always"},
    {"id": "TWR-003", "section": "TOWERS", "unlock": {"towers": 1}},
    {"id": "TWR-004", "section": "TOWERS", "unlock": {"data": 2}},
    {"id": "TWR-005", "section": "TOWERS", "unlock": {"towers": 2}},
    {"id": "STM-001", "section": "STORMS", "unlock": "always"},
    {"id": "STM-002", "section": "STORMS", "unlock": "always"},
    {"id": "STM-003", "section": "STORMS", "unlock": {"storms": 1}},
    {"id": "STM-004", "section": "STORMS", "unlock": {"storms": 2}},
    {"id": "HST-001", "section": "HISTORY", "unlock": "always"},
    {"id": "HST-002", "section": "HISTORY", "unlock": "always"},
    {"id": "HST-003", "section": "HISTORY", "unlock": {"data": 3}},
    {"id": "HST-004", "section": "HISTORY", "unlock": {"level": 1}},
    {"id": "HST-005", "section": "HISTORY", "unlock": {"data": 5}},
]


_BY_SECTION: dict[str, list[dict]] = {
    s: [e for e in ENTRIES if e["section"] == s]
    for s in SECTIONS
    if s not in ("LOGS", "SETTINGS")
}


class TerminalSystem:


    def __init__(self) -> None:
        self.biomes_visited: set[str] = set()
        self.storms_survived: int = 0
        self.read_ids: set[str] = set()

    def notify_biome(self, biome: str) -> None:
        self.biomes_visited.add(biome)

    def notify_storm(self) -> None:
        self.storms_survived += 1

    def get_entries(self, section: str, gs: dict) -> list[dict]:
        if section == "LOGS":
            return self._generate_logs(gs)
        if section == "SETTINGS":
            return self._settings_entries()
        return [self._localize(e) for e in _BY_SECTION.get(section, []) if self._is_unlocked(e, gs)]

    def get_all_for_section(self, section: str, gs: dict) -> list[dict]:
        """All entries (locked + unlocked) for list display."""
        if section == "LOGS":
            return self._generate_logs(gs)
        if section == "SETTINGS":
            return self._settings_entries()
        return [self._localize(e) for e in _BY_SECTION.get(section, [])]

    def is_locked(self, entry: dict, gs: dict) -> bool:
        if entry.get("_dynamic") or entry.get("_settings"):
            return False
        return not self._is_unlocked(entry, gs)

    def _is_unlocked(self, entry: dict, gs: dict) -> bool:
        u = entry.get("unlock", "always")
        if u == "always":
            return True
        if not isinstance(u, dict):
            return False
        if "biome" in u and u["biome"] not in self.biomes_visited:
            return False
        if "storms" in u and self.storms_survived < u["storms"]:
            return False
        if "towers" in u and gs.get("towers_activated", 0) < u["towers"]:
            return False
        if "data" in u and gs.get("data_fragments", 0) < u["data"]:
            return False
        if "level" in u and gs.get("station_level", 0) < u["level"]:
            return False
        return True

    def mark_read(self, entry_id: str) -> None:
        self.read_ids.add(entry_id)

    def is_read(self, entry_id: str) -> bool:
        return entry_id in self.read_ids

    @staticmethod
    def _localize(e: dict) -> dict:
        from systems.localization import get as loc_get
        eid = e["id"]
        loc_data = loc_get(f"terminal_entries.{eid}") or {}
        return {
            **e,
            "title":     loc_data.get("title", eid),
            "file_code": loc_data.get("file_code", eid),
            "lines":     loc_data.get("lines", []),
        }

    @staticmethod
    def _settings_entries() -> list[dict]:
        from systems.localization import t
        return [{"id": "SETTINGS-LANG", "_settings": True,
                 "title": t("settings.title"), "file_code": t("settings.file_code")}]

    def _generate_logs(self, gs: dict) -> list[dict]:
        from systems.localization import t
        station = gs.get("station")
        _lvl_keys = ["level_offline", "level_minimal", "level_partial", "level_operational"]
        lvl_label = t(f"station_ui.{_lvl_keys[min(3, gs.get('station_level', 0))]}")

        all_biomes = ["DUNES", "ROCKS", "MAGNETIC", "SHADOW"]
        unexplored = [b for b in all_biomes if b not in self.biomes_visited]
        biome_lines: list[str] = [t("logs.biome_survey_header"), ""]
        if self.biomes_visited:
            biome_lines += [f"  [{b}] — {t('logs.visited_tag')}" for b in sorted(self.biomes_visited)]
        else:
            biome_lines.append(f"  {t('logs.no_biomes')}")
        biome_lines += ["", t("logs.unexplored_header")]
        if unexplored:
            biome_lines += [f"  [{b}] — {t('logs.unknown_tag')}" for b in unexplored]
        else:
            biome_lines.append(f"  {t('logs.all_surveyed')}")

        return [
            {
                "id": "LOG-STATUS", "_dynamic": True,
                "title":     t("logs.status_title"),
                "file_code": t("logs.status_file"),
                "lines": [
                    t("logs.status_header"),
                    "",
                    f"{t('logs.biomes_explored')}  : {len(self.biomes_visited)} / 4",
                    f"{t('logs.towers_activated')} : {gs.get('towers_activated', 0)}",
                    f"{t('logs.storms_survived')}  : {self.storms_survived}",
                    f"{t('logs.resources_found')}  : {gs.get('resources_collected', 0)}",
                    "",
                    t("logs.inventory_header"),
                    f"  {t('logs.salvage_label')}     : {station.salvage if station else 0}",
                    f"  {t('logs.data_label')}   : {station.data_fragments if station else 0}",
                    f"  {t('logs.relay_label')} : {station.relay_components if station else 0}",
                    f"  {t('logs.ancient_label')}   : {station.ancient_tech if station else 0}",
                    "",
                    f"{t('logs.level_header')} {lvl_label}",
                    "",
                    t("logs.status_active"),
                ],
            },
            {
                "id": "LOG-BIOMES", "_dynamic": True,
                "title":     t("logs.biome_title"),
                "file_code": t("logs.biome_file"),
                "lines":     biome_lines,
            },
        ]
