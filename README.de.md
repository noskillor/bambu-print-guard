# bambu-print-guard

**Lokale, kostenlose KI-Fehlererkennung für Bambu-Lab-Drucker in Home Assistant.**

*English: [README.md](README.md)*

bambu-print-guard beobachtet während eines Drucks die Druckerkamera, erkennt Spaghetti,
abgelöste Teile und Klumpen mit dem Open-Source-Modell von
[Obico](https://github.com/TheSpaghettiDetective/obico-server) und schickt eine
**Push-Nachricht mit Knöpfen** über die Home-Assistant-App:

- 📸 Foto mit markierter Fehlerstelle
- 🔢 Schicht, ab der der Fehler begann, mit **exakter Z-Höhe** aus dem G-Code
- ✂️ **letzte gute Schicht** – dort in Bambu Studio / Orca schneiden, Rest drucken, ankleben
- ⏸️ **Pausieren / Fortsetzen** direkt in der Nachricht
- 🧠 Live-Ansicht, was die KI sieht, und Score-Verlauf im Dashboard

Alles läuft lokal: keine Cloud, kein Abo, keine Grafikkarte nötig. Funktioniert mit
Druckern im **LAN-only- / Developer-Modus**.

## Funktionsweise

1. Solange der Drucker `running` meldet, holt der Guard alle 10 s ein Kamerabild aus HA.
2. Das Obico-Modell liefert Fundstellen mit Wahrscheinlichkeit → Score pro Bild.
3. Der Score wird geglättet; für einen Alarm müssen mehrere Bilder hintereinander
   auffällig sein – einzelne Reflexe lösen nichts aus.
4. Bei einem Alarm ruft der Guard einen HA-Webhook auf; das Blueprint lädt das Bild
   und verschickt die Nachricht.

Gemessen auf Intel i5-9500 (2 Kerne): ~0,35 s pro Bild, ~360 MB RAM für das Modell.

## Voraussetzungen

- Home Assistant mit [ha-bambulab](https://github.com/greghesp/ha-bambulab) (auch im
  LAN-only-Modus) und der Companion-App auf dem Handy
- Ein Rechner mit Docker *oder* Debian (Proxmox-LXC, VM, NAS, Mini-PC, Raspberry Pi 4/5),
  ca. 1 GB freier RAM während des Drucks
- Getestet mit **P1S**; andere Bambu-Drucker sollten gehen, solange HA eine Kamera-Entität
  und einen Druckstatus-Sensor hat.

## Installation

**Variante A – Docker Compose (empfohlen)**

```bash
git clone https://github.com/noskillor/bambu-print-guard.git
cd bambu-print-guard
mkdir -p config data
cp config.example.json config/config.json   # Entitäts-IDs + public_url anpassen
nano config/ha_token                         # HA-Long-Lived-Token einfügen
docker compose up -d --build
```

**Variante B – Debian / Proxmox-LXC**

```bash
git clone https://github.com/noskillor/bambu-print-guard.git
cd bambu-print-guard
sudo bash deploy/lxc/install.sh
```

Optional startet der Proxmox-Host den Container nur während eines Drucks:
[docs/proxmox.md](docs/proxmox.md).

**Konfiguration:** In `config.json` mindestens die Entitäts-IDs deines Druckers und
`public_url` (Adresse, unter der HA den Guard erreicht, z. B. `http://192.168.1.50:8098`)
eintragen. Bei deutscher HA-Sprache heißen die Sensoren z. B. `sensor.<drucker>_druckstatus`,
`sensor.<drucker>_aktuelle_schicht`, `sensor.<drucker>_gesamtzahl_der_schichten`.
Alle Optionen: [docs/configuration.md](docs/configuration.md).

**Home Assistant einrichten:** [docs/home-assistant.md](docs/home-assistant.md) –
ein Helfer, drei kleine Integrationen, zwei Blueprints, ein Dashboard-Reiter.

## Lizenzen & Danksagung

- Erkennungsmodell und ML-Dienst: **[Obico](https://github.com/TheSpaghettiDetective/obico-server)**
  (AGPL-3.0). Dieses Repository enthält **keinen** Obico-Code und keine Modelldateien; der
  Container wird beim Nutzer direkt aus dem offiziellen Obico-Repository gebaut. Kein offizielles
  Projekt von Obico oder Bambu Lab.
- Code in diesem Repository: [MIT-Lizenz](LICENSE).
