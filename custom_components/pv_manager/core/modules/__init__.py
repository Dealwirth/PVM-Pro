"""Der interne PV-Manager-Modul-Store ("Addons").

Diese Module sind **keine** Home-Assistant-Add-ons und keine
Supervisor-Container. Es sind gebündelte, versionierte Funktionspakete der
PV-Manager-Oberfläche; jedes kann einzeln ein- oder ausgeschaltet werden,
ohne das Grundsystem zu entfernen.

Layout
------

``_spec.py``
    Datenklassen ``ModuleSpec`` und ``ModuleCategory``.
``<kategorie>/<module_id>.py``
    **Ein Addon = eine Datei.** Jede Datei exportiert eine ``SPEC`` und
    trägt oben eine Erklärung, was das Addon tut und wo es einhängt.
``_registry.py``
    Setzt ``MODULE_SPECS`` zusammen und hält die Helferfunktionen.

Diese ``__init__.py`` ist die stabile öffentliche Schnittstelle. Interner
Code und Tests importieren immer dieses Paket, niemals Unterdateien direkt –
dann können Dateien umgebaut werden, ohne Aufrufstellen zu brechen.
Anleitung für eigene Addons: ``docs/ADDONS.md``.
"""

from __future__ import annotations

from ._registry import (
    CORE_MODULE,
    CORE_MODULE_ID,
    MODULE_SPECS,
    MODULES_BY_ID,
    default_enabled_modules,
    dependents_of,
    resolve_dependencies,
    store_cards,
)
from ._spec import ModuleCategory, ModuleSpec

__all__ = [
    "CORE_MODULE",
    "CORE_MODULE_ID",
    "MODULES_BY_ID",
    "MODULE_SPECS",
    "ModuleCategory",
    "ModuleSpec",
    "default_enabled_modules",
    "dependents_of",
    "resolve_dependencies",
    "store_cards",
]
