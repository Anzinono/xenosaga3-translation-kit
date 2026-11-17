"""Sammelt Glossar-Kandidaten und schreibt text/de/glossar.csv.

Quellen:
  - Datenbank-Titel (text/en/datenbank.csv, feld=titel) mit Kategorie
  - Sprechernamen [Name] am Anfang der Dialoge (text/en/skripte.csv)
  - Spielsystem-Begriffe (fest eingetragen, siehe SYSTEM)

Vorschläge für begriff_de stehen in VORSCHLAG. Ein vorhandenes glossar.csv wird
nicht überschrieben, wenn dort schon begriff_de/status von Hand gepflegt sind:
Einträge aus der Datei haben Vorrang, neue Kandidaten werden ergänzt.

Aufruf: python -I tools/glossar_kandidaten.py
"""
import collections
import csv
import pathlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sprache import LANG, TEXT_DIR  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
EN = ROOT / "text" / "en"
OUT = TEXT_DIR / "glossar.csv"
SPALTEN = ["begriff_en", "begriff_de", "art", "quelle", "vorkommen", "status", "hinweis"]

KAT_ART = {
    "Characters": "Person", "Cultural": "Fachbegriff", "Events": "Ereignis",
    "Locations": "Ort", "Weapons": "Waffe/Technik", "Organizations": "Organisation",
    "Unknown": "Mythos/Technik", "Town Report": "Nebenhandlung", "Story": "Rückblick",
    "Tutorial": "Kampfsystem",
}

# Grundsatzfragen, auf die "offen" verweist (Nummern wie in docs/stil.md)
G_REALIAN = "Frage G1: Realian/Realians oder Realianer?"
G_ORT = "Frage G2: Ortsnamen mit Zahl-/Eigenschaftswort übersetzen?"
G_KAMPF = "Frage G3: Kampfbegriffe englisch lassen?"
G_HUMOR = "Frage G4: Witzfiguren/Spitznamen übersetzen?"

# begriff_en: (begriff_de, status, hinweis)   status: fest | vorschlag | offen
V = {}
def v(en, de, status="vorschlag", hinweis=""):
    V[en] = (de, status, hinweis)

# --- Grundbegriffe der Serie: bleiben ---
for t in ["KOS-MOS", "chaos", "MOMO", "T-elos", "Gnosis", "Zohar", "U-DO", "U-TIC", "U.M.N.",
          "E.S.", "URTV", "A.G.W.S.", "A.M.W.S.", "M.W.S.", "D.S.S.S.", "V.L.V.", "J.M.I.",
          "C.S.R.C.", "C.P.C.", "F.S.I.", "E.A.P.F.", "UNP", "ECM", "ECCM", "NATARAJA", "Nexus",
          "Nexus 6", "Testament", "Anima", "Ormus", "Scientia", "Vector", "Vector Industries",
          "Hyams", "Labyrinthos", "Merkabah", "Proto Merkabah", "Omega", "Proto Omega",
          "Omega Id", "Omega Universitas", "Omega Metempsychosis", "Omega Res Novae",
          "Natus Glacies", "Natus Tellus", "Natus Flamma", "Natus Lumen", "Pleroma",
          "Rennes-le-Château", "Dämmerung", "Erde Kaiser", "Wellgunde", "Woglinde", "Floßhilde",
          "Durandal", "Elsa", "Lemegeton", "Yeshua", "Joshua", "Zarathustra", "Abyss", "Euphrates",
          "Encephalon", "Grimoire Verum", "Prodigium", "Salvator", "Procurator", "Interlink",
          "Draper", "Archon", "Miltia", "Abraxas", "Michtam", "Y-Data", "Leupold", "Pellegri",
          "DIG-β (Beta)", "PT Cartridge", "VX Series", "AG Series", "Auto-Tech"]:
    v(t, t, "fest", "Eigenname/Fachbegriff der Serie, bleibt englisch")
v("PT Cartridge", "PT-Kartusche", "vorschlag")
v("VX Series", "VX-Serie"); v("AG Series", "AG-Serie"); v("DIG-β (Beta)", "DIG-β (Beta)", "fest")
v("Auto-Tech", "Auto-Tech", "fest", "Plural: Auto-Techs")

v("Realian", "Realianer", "bestaetigt", G_REALIAN + " Entscheidung 2026-11-15: Realianer (Plural Realianer)")
v("Realians", "Realianer", "bestaetigt", G_REALIAN)
v("100-Series Realian", "Realianer der 100er-Serie", "bestaetigt", G_REALIAN)
v("100-Series Observational Unit", "Beobachtungseinheit der 100er-Serie")
v("100-Series", "100er-Serie")

# --- Personen mit beschreibendem Zusatz ---
v("Testament [Blue]", "Testament [Blau]"); v("Testament [Red]", "Testament [Rot]")
v("Testament [Black]", "Testament [Schwarz]"); v("Testament [White]", "Testament [Weiß]")
v("Blue Testament", "Blaues Testament"); v("Red Testament", "Rotes Testament")
v("Kevin Winnicot [Child]", "Kevin Winnicot [Kind]"); v("Shion Uzuki [Child]", "Shion Uzuki [Kind]")
v("Kevin's Mother", "Kevins Mutter")
v("KOS-MOS [Archetype]", "KOS-MOS [Archetyp]"); v("KOS-MOS [Test Type]", "KOS-MOS [Testtyp]")
v("KOS-MOS [Combat Frame]", "KOS-MOS [Kampfrahmen]")
v("Lieutenant Commander", "Korvettenkapitän", "offen", "Dienstgrad, Kontext prüfen")
v("Captain Moriyama", "Kapitän Moriyama")
v("Patriarch", "Patriarch")
v("Professor", "Professor", "fest")
v("Boss", "Boss", "fest")
v("Jr.", "Jr.", "fest")
v("Nephilim", "Nephilim", "fest")
v("Kirschwasser", "Kirschwasser", "fest", "Plural im Englischen: Kirschwassers → dt. Kirschwasser")
v("young Kevin", "junger Kevin"); v("child Kevin", "kleiner Kevin"); v("young Shion", "junge Shion")
v("young man", "junger Mann"); v("young girl", "junges Mädchen"); v("old man", "alter Mann")
v("Boy", "Junge"); v("Child", "Kind"); v("Soldier", "Soldat")
v("Federation Soldier", "Föderationssoldat"); v("Ormus Soldier", "Ormus-Soldat")
v("U-TIC Soldier", "U-TIC-Soldat"); v("U-TIC Researcher", "U-TIC-Forscher")
v("Vector Researcher", "Vector-Forscher"); v("Zohar Researcher", "Zohar-Forscher")
v("Security Guard", "Wachmann"); v("News Reporter", "Nachrichtensprecher")
v("Security Management", "Sicherheitsverwaltung"); v("Information", "Information")
v("Console", "Konsole"); v("Warning", "Warnung"); v("WARNING", "WARNUNG"); v("CAUTION", "ACHTUNG")
v("Combat Frame", "Kampfrahmen"); v("Archetype", "Archetyp"); v("Test Type", "Testtyp")

# --- Witzfiguren / Nebenhandlung ---
v("Coconut Monkey", "Coconut Monkey", "offen", G_HUMOR + " Alternative: Kokosaffe")
v("CUSTOM COCONUT #1", "CUSTOM COCONUT #1", "offen", G_HUMOR)
v("CUSTOM COCONUT #2", "CUSTOM COCONUT #2", "offen", G_HUMOR)
v("Dark Professor", "Dunkler Professor", "offen", G_HUMOR)
v("Other Professor", "Anderer Professor", "offen", G_HUMOR)
v("Dark Erde Kaiser", "Dunkler Erde Kaiser", "offen", G_HUMOR)
v("Dark Professor's Secret Laboratory", "Geheimlabor des Dunklen Professors", "offen", G_HUMOR)
v("Erde Kaiser Sigma", "Erde Kaiser Sigma", "fest"); v("Erde Kaiser Fury", "Erde Kaiser Fury", "offen", G_HUMOR)
v("Erde Kaiser Σ", "Erde Kaiser Σ", "fest")
v("Life-Sized Bunnie Plushy", "Lebensgroßer Bunnie-Plüsch")
v("Mobile Fortress Elsa Project", "Projekt Mobile Festung Elsa")
v("Assistant Number 2", "Assistent Nr. 2"); v("Assistant Number 3", "Assistent Nr. 3")
v("Robot Academy", "Roboterakademie"); v("Frying Pan", "Bratpfanne")
v("Forbidden Device", "Verbotenes Gerät"); v("Schrodinger", "Schrödinger")
v("Sequencer", "Sequenzer"); v("Decoder", "Decoder"); v("Segment Address", "Segmentadresse")
v("Segment File", "Segmentdatei"); v("Hoshino", "Hoshino", "fest")
v("Challenge Coupon Association Official Shop", "Offizieller Laden des Challenge-Coupon-Verbands")
v("Quincy's Select Shop", "Quincys Auswahlladen")

# --- Orte ---
for p in ["Atalya", "Abraxas", "Ariadne", "Carioca", "Keltia", "Zavarov", "Senir", "Tessedora", "Michtam"]:
    v("Planet " + p, "Planet " + p)
v("Second Miltian", "Zweit-Miltianisch", "vorschlag", "Adjektiv, im Satz anpassen")
v("Second Miltia", "Zweites Miltia", "bestaetigt", G_ORT + " eingedeutscht")
v("Fifth Jerusalem", "Fünftes Jerusalem", "bestaetigt", G_ORT + " eingedeutscht")
v("Lost Jerusalem", "Lost Jerusalem", "bestaetigt", G_ORT + " bleibt englisch (Nutzer: nicht „Verlorenes Jerusalem“)")
v("Old Miltia", "Alt-Miltia", "bestaetigt", G_ORT + " eingedeutscht")
v("Sunken City", "Versunkene Stadt")
v("Archon Spaceport", "Raumhafen Archon"); v("Archon Cathedral", "Kathedrale von Archon")
v("Archon Zone", "Archon-Zone"); v("Archon Map", "Karte von Archon")
v("Isolated Research Facility", "Abgelegene Forschungseinrichtung")
v("S-Line Division", "S-Linien-Abteilung"); v("Ormus Stronghold", "Ormus-Festung")
v("Isolation Area", "Isolationsbereich"); v("Orbital Elevator", "Orbitalaufzug")
v("Orbital Station", "Orbitalstation"); v("Gedalya Autonomous State", "Autonomer Staat Gedalya")
v("Sakura's House", "Sakuras Haus")
v("Acute Neurosis Treatment Facility", "Behandlungseinrichtung für akute Neurosen")
v("Personality Reconditioning Facility", "Einrichtung zur Persönlichkeitsrekonditionierung")
v("Dabrye Mine", "Dabrye-Mine")
v("C.A.T. Testing Ground", "C.A.T.-Testgelände")
v("Consolidated Advanced Technology Testing Ground", "Vereintes Testgelände für Hochtechnologie")
v("Lake Turkana", "Turkana-See"); v("The Old Church", "Die alte Kirche")
v("Pedea Island", "Insel Pedea"); v("Miltian Hierocracy", "Miltianische Hierokratie")
v("Miltian Autonomous State", "Autonomer Staat Miltia"); v("Miltian Space", "Miltianischer Raum")
v("Moby Dick's Café", "Moby Dick's Café", "fest", "Ladenname bleibt")
v("U.M.N. Administration Bureau", "U.M.N.-Verwaltungsamt")
v("U.M.N. Control Center", "U.M.N.-Kontrollzentrum")
v("Yuriev Institute", "Yuriev-Institut")
v("University of Bormeo", "Universität Bormeo")

# --- Organisationen ---
v("Galaxy Federation", "Galaktische Föderation"); v("Federation", "Föderation")
v("Federation Fleet", "Föderationsflotte"); v("Federation Parliament", "Föderationsparlament")
v("Federation Police", "Föderationspolizei"); v("Federation Police Academy", "Föderationspolizeiakademie")
v("Federation Council", "Föderationsrat")
v("Federation Emergency Powers Act", "Notstandsgesetz der Föderation")
v("Immigrant Fleet", "Einwandererflotte")
v("Vector First R&D Division", "Vector, 1. F&E-Abteilung")
v("Vector Second R&D Division", "Vector, 2. F&E-Abteilung")
v("Vector Third R&D Division", "Vector, 3. F&E-Abteilung")
v("Special Technology Advancement", "Abteilung für Sondertechnologie")
v("Kukai Foundation", "Kukai-Stiftung", "bestaetigt", G_ORT + " eingedeutscht")
v("Public Safety Commission", "Kommission für öffentliche Sicherheit")
v("Ziggurat Industries", "Ziggurat Industries", "fest")
v("Autonomous State", "Autonomer Staat"); v("Executive Committee", "Exekutivkomitee")
v("Contact Subcommittee", "Kontakt-Unterausschuss")
v("Tactical Sim Lab", "Taktisches Simulationslabor")
v("117th Marine Division", "117. Marinedivision")
v("1875th Special Ops Command", "1875. Spezialeinsatzkommando")
v("34th Special Transport Troop", "34. Spezialtransporttruppe")
v("474th Spec Ops Fleet", "474. Spezialeinsatzflotte")
v("Anti-Patriarch Faction", "Anti-Patriarchen-Fraktion")
v("Zohar Project", "Zohar-Projekt"); v("U-TIC Organization", "U-TIC-Organisation")
v("Special Weapon Development Division", "Abteilung für Sonderwaffenentwicklung")

# --- Fachbegriffe ---
v("Android", "Androide"); v("Überhumans", "Übermenschen", "offen", "Nietzsche-Bezug; im Original deutsch angelehnt")
v("Imaginary Pocket", "Imaginäre Tasche"); v("Interconnection", "Interkonnektion")
v("Ethelle", "Ethelle", "fest"); v("Environmental Bug", "Umweltfehler")
v("Carnegie Structure Law", "Carnegie-Strukturgesetz"); v("Camelle", "Camelle", "fest")
v("Curry", "Curry"); v("Curry Gruel", "Curry-Brei")
v("Enhanced Memory Model", "Modell mit erweitertem Gedächtnis")
v("Klein Point", "Klein-Punkt"); v("Cage Partition", "Käfigtrennung")
v("Gate Out", "Gate-Austritt"); v("Gate Jump", "Gate-Sprung")
v("Species Preservation Act", "Artenschutzgesetz"); v("Trade Column", "Handelssäule")
v("Connection Gear", "Verbindungsgerät"); v("Commercial Model", "Handelsmodell")
v("Recycler", "Recycler"); v("Cybernetic Engineering", "Kybernetische Technik")
v("Cyborg", "Cyborg"); v("Geocrystal", "Geokristall"); v("Geodesic Structure", "Geodätische Struktur")
v("Auto-Mode", "Automodus"); v("Seraphim Sisters", "Seraphim-Schwestern")
v("Safe House", "Unterschlupf"); v("Absolute Standard Time", "Absolute Standardzeit")
v("Absolute Coordinates", "Absolute Koordinaten"); v("Postwar Reparations", "Kriegsreparationen")
v("Device Activator Syringe", "Geräteaktivator-Spritze")
v("Level 7 Personality Reconditioning", "Persönlichkeitsrekonditionierung Stufe 7")
v("Diving Device", "Tauchgerät"); v("Dive", "Tauchgang"); v("Dive Pod", "Tauchkapsel")
v("Dive Unit", "Tauchgerät", "vorschlag", "Unterschied zu Diving Device prüfen")
v("Direct Approach", "Direktzugang"); v("Dummy Protocol", "Dummy-Protokoll")
v("Central Computer Pieta", "Zentralrechner Pietà")
v("Abstract Cognitive Function", "Abstrakte kognitive Funktion")
v("Central Nervous System Disorder", "Störung des Zentralnervensystems")
v("Ultra Wide Range Hilbert", "Ultra-Weitbereichs-Hilbert")
v("Maintenance Box", "Wartungsbox"); v("DME Addiction", "DME-Sucht")
v("Disconnect", "Trennung"); v("Transfer Wave", "Transferwelle"); v("Transfer System", "Transfersystem")
v("Transgenic Type", "Transgener Typ"); v("Neural Monitoring", "Neuronale Überwachung")
v("Heat Death", "Wärmetod"); v("Hyperspace", "Hyperraum")
v("Paradigm Contamination", "Paradigmenkontamination")
v("Hilbert Effect", "Hilbert-Effekt"); v("Primer Walking", "Primer Walking", "offen", "Fachbegriff, unklar")
v("Brainjack", "Brainjack"); v("Proprietary", "Proprietär")
v("Divide and Rule Measure", "Maßnahme „Teile und herrsche“")
v("Holographic Network", "Holografisches Netzwerk")
v("Holographic Mail Terminal", "Holografisches Mail-Terminal")
v("Mass Driver", "Massenbeschleuniger"); v("Miltia Charter", "Charta von Miltia")
v("Artificial Personality Layer", "Künstliche Persönlichkeitsschicht")
v("U.M.N. Transfer Column", "U.M.N.-Transfersäule"); v("U.M.N. Pulse", "U.M.N.-Impuls")
v("Life Recycling Law", "Lebensrecyclinggesetz")
# Ereignisse
v("Nursing Plant Incident", "Zwischenfall in der Pflegeanlage")
v("Space-Time Anomaly", "Raum-Zeit-Anomalie"); v("Gnosis Terrorism", "Gnosis-Terrorismus")
v("Ambassador Lock-Up Incident", "Botschafter-Geiselnahme")
v("Zoar Incident", "Zoar-Zwischenfall"); v("Plan 31", "Plan 31"); v("Plan 401", "Plan 401")
v("Miltian Conflict", "Miltianischer Konflikt"); v("Link Experiment", "Verbindungsexperiment")
v("Disappearance of Planet Ariadne", "Verschwinden des Planeten Ariadne")
# Waffen/Technik
v("27-Series Asura", "Asura der 27er-Serie"); v("Attract Inhibitor", "Anziehungshemmer")
v("Amplifier", "Verstärker"); v("Woglinde II", "Woglinde II", "fest")
v("A.M.W.S. [Jin's]", "A.M.W.S. [Jins]"); v("A.M.W.S. [Doctus's]", "A.M.W.S. [Doctus']")
v("A.M.W.S. Scutum", "A.M.W.S. Scutum"); v("A.M.W.S. Pilum", "A.M.W.S. Pilum")
v("Revised M.W.S.", "Überarbeitetes M.W.S."); v("Condenser", "Kondensator"); v("Generator", "Generator")
v("Tactical Assault Ship Merkabah", "Taktisches Angriffsschiff Merkabah")
v("Phase Transfer Cannon", "Phasentransferkanone"); v("Target Drone", "Zieldrohne")
v("Secondary Weapons System", "Sekundärwaffensystem"); v("Tertiary Weapons System", "Tertiärwaffensystem")
v("Anti-U-DO Shift", "Anti-U-DO-Verschiebung"); v("Mobile Dinah Interface", "Mobile Dinah-Schnittstelle")
v("Designer Children", "Designerkinder"); v("Point Man", "Vorhut"); v("Macrophage", "Makrophage")
v("Infected URTV", "Infizierter URTV")
for n in ["623", "666", "667", "668", "669"]:
    v("URTV Unit Number " + n, "URTV Einheit Nr. " + n)
v("Standard URTV", "Standard-URTV"); v("Variant URTV", "URTV-Variante")
v("Rhine Maiden", "Rheintochter", "vorschlag", "Wagner-Bezug (Woglinde, Wellgunde, Floßhilde)")
v("Logical Drive", "Logisches Laufwerk"); v("Logical Drive Pod", "Logische Laufwerkskapsel")
# Mythos/Technik
v("Vessel of Anima", "Gefäß der Anima"); v("Blood of Abraxas", "Blut von Abraxas")
v("Abel's Ark", "Abels Arche"); v("Arbiter Code", "Schiedsrichter-Code")
v("Inquisitors", "Inquisitoren"); v("U-DO Simulator", "U-DO-Simulator")
v("Original Zohar", "Ur-Zohar", "offen", "Alternative: Original-Zohar")
v("Imaginary Space", "Imaginärer Raum"); v("Gnosis Transformation", "Gnosis-Verwandlung")
v("Gnosis Phenomenon", "Gnosis-Phänomen"); v("Gnosis [Cathedral Ship]", "Gnosis [Kathedralenschiff]")
v("Gnosis [Porter]", "Gnosis [Träger]")
v("KOS-MOS Archetype Basic Theory", "Grundtheorie des KOS-MOS-Archetyps")
v("Thirteenth Key", "Dreizehnter Schlüssel"); v("Pilgrimage Meeting", "Pilgerversammlung")
v("Pilgrimage Fleet", "Pilgerflotte"); v("Executioner", "Henker")
v("Zohar Emulator", "Zohar-Emulator"); v("People of Zohar", "Volk des Zohar")
v("Compass of Order and Chaos", "Kompass von Ordnung und Chaos")
v("Secret Data", "Geheime Daten"); v("Net Preacher", "Netzprediger")
v("Song of Nephilim", "Lied der Nephilim"); v("Whitening", "Weißung", "offen", "alchemistischer Begriff (Albedo)")
v("Anti-U-DO Waveforms", "Anti-U-DO-Wellenformen"); v("Program Canaan", "Programm Canaan")
v("Pendant", "Anhänger"); v("Maiden of Mary", "Maria-Jungfrau", "offen", "Kontext prüfen")
v("Dimension Shift", "Dimensionsverschiebung"); v("Link Master", "Link-Master")
v("Red Dragon", "Roter Drache")

# --- Kampfsystem / Tutorial ---
v("Save Points", "Speicherpunkte"); v("Destroying Objects", "Objekte zerstören")
v("Segments", "Segmente"); v("Encounters", "Begegnungen"); v("Traps", "Fallen")
v("Skill Line", "Skill-Linie", "bestaetigt", G_KAMPF)
v("Character Battle Commands", "Kampfbefehle (Charaktere)")
v("Character Parameters", "Parameter (Charaktere)")
v("Boost", "Boost", "bestaetigt", G_KAMPF); v("Break", "Break", "bestaetigt", G_KAMPF)
v("Character Special Moves", "Spezialangriffe (Charaktere)")
v("Target Control", "Zielsteuerung"); v("Character Characteristics", "Eigenschaften (Charaktere)")
v("Character Types", "Charaktertypen"); v("E.S. Battle Commands", "Kampfbefehle (E.S.)")
v("E.S. Parameters", "Parameter (E.S.)"); v("E.S. Attack Methods", "Angriffsarten (E.S.)")
v("Enemy Count", "Gegneranzahl"); v("E.S. Special Moves", "Spezialangriffe (E.S.)")
v("Chains", "Ketten"); v("Team Combos", "Team-Kombos")
v("Enemy Classes and Characteristics", "Gegnerklassen und Eigenschaften")
v("Elements and Types of Attacks", "Elemente und Angriffsarten")
v("Status Enhancements", "Statusverbesserungen"); v("Status Ailments", "Statusveränderungen")
v("Finish Strike", "Finish Strike", "bestaetigt", G_KAMPF)
v("Back Attack", "Rückenangriff")
v("Special Attack", "Spezialangriff"); v("Anima Awakening", "Anima-Erweckung")

# --- Rückblick ---
v("End of EPISODE II to the present", "Vom Ende von EPISODE II bis heute")
v("Suou Uzuki's PDA", "Suou Uzukis PDA")
v("Militan Conflict Report", "Bericht zum Miltianischen Konflikt", "vorschlag", "Original hat Tippfehler „Militan“")

# --- Sprecher, die Schilder/Geräte/Orte sind ---
for en, de in [
    ("John Bunnie", "John Bunnie"), ("Bunnie Bob", "Bunnie Bob"),
    ("Scott's Console", "Scotts Konsole"), ("Professor's Console", "Konsole des Professors"),
    ("Weapon System Data Display Console", "Datenkonsole Waffensystem"),
    ("Weapon System Maintenance Console", "Wartungskonsole Waffensystem"),
    ("Observer Communications Console", "Kommunikationskonsole Beobachter"),
    ("Supervisor Communications Console", "Kommunikationskonsole Aufsicht"),
    ("Miltia City Planning Corp.", "Stadtplanung Miltia AG"), ("Durandal Loop Line", "Durandal-Ringbahn"),
    ("Realian Calibration Cylinder", "Realianer-Kalibrierzylinder"), ("Realian Unit Monitor", "Realianer-Monitor"),
    ("C.A.T. Testing Ground Information Board", "Infotafel C.A.T.-Testgelände"),
    ("Business District Gate", "Tor Geschäftsviertel"), ("Elsa Directory", "Elsa-Wegweiser"),
    ("Transport Conveyor Belt", "Transportband"), ("Miltia Waterworks Management Office", "Wasserwerksverwaltung Miltia (Büro)"),
    ("Miltia Waterworks Management", "Wasserwerksverwaltung Miltia"),
    ("Door Lock", "Türschloss"), ("Emergency Sub-Generator", "Notstromgenerator"),
    ("Core Maintenance Lift", "Wartungslift Kern"), ("Honeycomb Protect Area", "Wabenschutzbereich"),
    ("Zohar Storage Room", "Zohar-Lagerraum"), ("Zohar Elevator", "Zohar-Aufzug"),
    ("Zohar Elevator Start-up Switch", "Startschalter Zohar-Aufzug"), ("Zohar Elevator Switch", "Schalter Zohar-Aufzug"),
    ("Secret Elevator", "Geheimaufzug"), ("Core Area", "Kernbereich"), ("Core Area Gate", "Tor Kernbereich"),
    ("Main Elevator", "Hauptaufzug"), ("Cockpit Direct Approach Elevator", "Direktaufzug Cockpit"),
    ("Direct Elevator", "Direktaufzug"), ("Dumping Elevator", "Abwurfaufzug"), ("Shaft Elevator", "Schachtaufzug"),
    ("Shaft Control Panel", "Schachtsteuerung"), ("Shaft Elevator Control Panel", "Steuerpult Schachtaufzug"),
    ("Entrance Station", "Station Eingang"), ("Demonstration Site Station", "Station Vorführgelände"),
    ("Vector Section Station", "Station Vector-Sektion"), ("Gnosis Storage Section Station", "Station Gnosis-Lager"),
    ("Special Weapon Development Division Station", "Station Sonderwaffenentwicklung"),
    ("Dock Station", "Station Dock"), ("Park Station", "Station Park"),
    ("Third Residential Area Station", "Station 3. Wohngebiet"), ("Isolation Area Station", "Station Isolationsbereich"),
    ("Old Transport Gate", "Altes Transporttor"), ("Health Department", "Gesundheitsamt"),
    ("Test Subject List", "Liste der Testpersonen"), ("Container Receiving System", "Containerannahme"),
    ("Labyrinthos Linear Train", "Labyrinthos-Linearbahn"), ("Staff Room", "Personalraum"),
    ("Emergency Barrier", "Notsperre"), ("Research Resource Transport Elevator", "Lastenaufzug Forschungsmaterial"),
    ("Research Resource Transport Elevator Switch", "Schalter Lastenaufzug Forschungsmaterial"),
    ("Zohar Isolation Research Ward - South Gate Switch", "Schalter Südtor Zohar-Isolationsstation"),
    ("Zohar Isolation Research Ward- South Gate", "Südtor Zohar-Isolationsstation"),
    ("Zohar Isolation Research Ward - North Gate", "Nordtor Zohar-Isolationsstation"),
    ("Ropeway", "Seilbahn"), ("Fifth Jerusalem Tourist Association", "Tourismusverband Fünftes Jerusalem"),
    ("Human Security", "Personenschutz"), ("Gravitational Control", "Schwerkraftsteuerung"),
    ("Global Security System for the Core Area", "Sicherheitssystem Kernbereich"),
    ("Propulsion System Foundation", "Antriebssystem-Fundament"), ("Worker Auto-Tech", "Arbeiter-Auto-Tech"),
    ("Entrance Lock", "Eingangssperre"), ("Centralized Computer System", "Zentrales Rechnersystem"),
    ("Power Control System", "Energiesteuerung"), ("Mobile Weapon Boarding Elevator", "Einstiegsaufzug Mobilwaffen"),
    ("Mobile Weapon Craft Boarding Elevator", "Einstiegsaufzug Mobilwaffen-Fahrzeuge"),
    ("Women's Cabin", "Frauenkabine"), ("Men's Cabin", "Männerkabine"),
    ("Security Management Room", "Raum der Sicherheitsverwaltung"), ("Power Distribution Crank", "Kurbel Stromverteilung"),
    ("W.R.C. (Wild Roller Coaster)", "W.R.C. (Wilde Achterbahn)"),
    ("W.R.C. (Wild Roller Coaster) Control Explanation", "W.R.C. (Wilde Achterbahn) – Steuerung"),
    ("Check Gate", "Kontrolltor"), ("Security System", "Sicherheitssystem"),
    ("Jacob Medical Imprinting", "Jacob Medical Imprinting"), ("L-10 Shelter Switch", "Schalter Schutzraum L-10"),
]:
    V.setdefault(en, (de, "vorschlag", "Sprechername eines Objekts"))
for t in ["A-1 Gate", "A-2 Gate"]:
    v(t, "Tor " + t[:3]); v(t + " Switch", "Schalter Tor " + t[:3])
for s in "ABCD":
    v(f"Merkabah Sector {s}", f"Merkabah, Sektor {s}")
    for n in "12":
        v(f"Merkabah Sector {s}-{n}", f"Merkabah, Sektor {s}-{n}")
for n in "1234":
    v(f"Console {n}", f"Konsole {n}")
for n in "123":
    v(f"Central Elevator {n}", f"Zentralaufzug {n}")
for e in ["Asher", "Zebulun", "Reuben", "Dinah"]:
    v(f"E.S. {e} Elevator", f"Aufzug E.S. {e}")

v("Bride Area Station", "Station Brautbereich", "offen", "Original „Bride“ – evtl. Tippfehler für Bridge, im Spiel prüfen")

# --- Spielsystem (Menüs, nicht in Datenbank-Titeln) ---
SYSTEM = [
    ("HP", "HP", "fest", "Kürzel bleiben"), ("EP", "EP", "fest", ""),
    ("Ether", "Äther", "vorschlag", "so schon im Probelauf"),
    ("Items", "Gegenstände", "vorschlag", "so schon im Probelauf"),
    ("Equip", "Ausrüstung", "vorschlag", "so schon im Probelauf"),
    ("Skill", "Skill", "bestaetigt", G_KAMPF),
    ("Formation", "Formation", "vorschlag", ""),
    ("Database", "Datenbank", "vorschlag", ""),
    ("Save Point", "Speicherpunkt", "vorschlag", ""),
    ("Segment Address", "Segmentadresse", "vorschlag", ""),
    ("Characters", "Charaktere", "vorschlag", "Datenbank-Kategorie, auch njDBcommon.bin"),
    ("Cultural", "Kultur", "vorschlag", "Datenbank-Kategorie"),
    ("Events", "Ereignisse", "vorschlag", "Datenbank-Kategorie"),
    ("Locations", "Orte", "vorschlag", "Datenbank-Kategorie"),
    ("Weapons", "Waffen", "vorschlag", "Datenbank-Kategorie"),
    ("Organizations", "Organisationen", "offen", "Datenbank-Kategorie; 14 Zeichen, länger als jedes Original (max. 13). Alternative: Gruppen"),
    ("Unknown", "Unbekannt", "vorschlag", "Datenbank-Kategorie"),
    ("Town Report", "Stadtbericht", "vorschlag", "Datenbank-Kategorie"),
    ("Story", "Handlung", "vorschlag", "Datenbank-Kategorie"),
    ("Tutorial", "Tutorial", "vorschlag", "Datenbank-Kategorie"),
]

GENERISCHE_EINZELWOERTER = {"Boy", "Child", "Soldier", "Console", "Information", "Warning", "Ropeway", "Professor"}


def lies(name):
    with open(EN / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main():
    db = lies("datenbank.csv")
    sk = lies("skripte.csv")
    alle_texte = []
    for n in ["skripte.csv", "datenbank.csv", "menue_txd.csv", "menue_bin.csv",
              "minispiel_rueckblick.csv", "untertitel.csv"]:
        alle_texte += [r["text_en"].replace("\\n", " ") for r in lies(n)]
    gross = "\n".join(alle_texte)

    kand = collections.OrderedDict()  # en -> (art, quelle)
    kat = None
    for r in sorted(db, key=lambda r: int(r["eintrag"])):
        if r["feld"] == "kategorie":
            kat = r["text_en"]
        if r["feld"] == "titel":
            t = r["text_en"].strip()
            if "�" in t or not t:
                continue
            if t.startswith(("History of Abraxas", "Federal Report", "EPISODE")):
                continue
            kand.setdefault(t, (KAT_ART.get(kat, "?"), "datenbank:" + (kat or "?")))
    sprecher = collections.Counter()
    for r in sk:
        m = re.match(r"\[([^\]]+)\]", r["text_en"])
        if m:
            sprecher[m.group(1).strip()] += 1
    for s, n in sprecher.most_common():
        if s in kand:
            kand[s] = (kand[s][0], kand[s][1] + "+sprecher")
            continue
        if re.match(r"(Federal Report|Observation Regarding) ", s):
            continue
        einzel = " " not in s and s[:1].isupper() and not s.isupper() and s not in GENERISCHE_EINZELWOERTER
        kand[s] = ("Person" if einzel or s in V and V[s][0] == s and V[s][1] == "fest" else "Sprecher/Objekt", "sprecher")
    for en, de, st, h in SYSTEM:
        kand.setdefault(en, ("Spielsystem", "menue"))
        V.setdefault(en, (de, st, h))

    # bestehende Datei: Handpflege hat Vorrang
    alt = {}
    if OUT.exists():
        with open(OUT, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                alt[r["begriff_en"]] = r

    zeilen = []
    for en, (art, quelle) in kand.items():
        if en in V:
            de, st, h = V[en]
        elif art == "Person" or en.split()[0] in {"E.S."}:
            de, st, h = en, "fest", "Name bleibt"
        elif re.match(r"Merkabah Sector|Console \d|Central Elevator \d|A-\d Gate", en):
            de, st, h = "", "vorschlag", "Schild/Objekt, beim Übersetzen der Dialoge festlegen"
        else:
            de, st, h = "", "vorschlag", "noch kein Vorschlag"
        if art == "Person" and en not in V:
            de, st, h = en, "fest", "Name bleibt"
        n = gross.count(en)
        z = {"begriff_en": en, "begriff_de": de, "art": art, "quelle": quelle,
             "vorkommen": str(n), "status": st, "hinweis": h}
        if en in alt and alt[en].get("status") in ("bestaetigt", "geaendert"):
            z.update({k: alt[en][k] for k in ("begriff_de", "status", "hinweis")})
        zeilen.append(z)
    for en, r in alt.items():  # von Hand ergänzte Begriffe behalten
        if en not in kand:
            zeilen.append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SPALTEN, delimiter=";")
        w.writeheader()
        w.writerows(zeilen)
    c = collections.Counter(z["status"] for z in zeilen)
    print(f"{len(zeilen)} Begriffe -> {OUT.relative_to(ROOT)}  ({dict(c)})")


if __name__ == "__main__":
    main()
