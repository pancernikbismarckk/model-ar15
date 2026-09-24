# weapon_ar15 — model 3D

Model 3D karabinka w układzie AR-15 odtworzony na podstawie zdjęcia referencyjnego i specyfikacji:
lufa 16,1", wolnopływające łoże 15" M-LOK z szyną Picatinny, kolba typu MOE SL (6 pozycji),
chwyt A2, polimerowy magazynek 30-nabojowy, składane przyrządy celownicze, tłumik płomienia A2.

**Bez oznaczeń producenta** — model nie zawiera żadnych napisów, logotypów, numerów seryjnych
ani oznaczeń bezpiecznika. Wszystkie nazwy obiektów są generyczne (`weapon_ar15`, `ar15_*`).

![z dodatkami](renders/weapon_ar15_3q_front.png)

![bez dodatków](renders/weapon_ar15_plain_3q.png)

## Pliki

| Plik | Opis |
|---|---|
| `weapon_ar15.blend` | scena Blendera (kolekcja `weapon_ar15`: broń, 4 dodatki, sockety) |
| `export/weapon_ar15.glb` | eksport glTF 2.0 (hierarchia, tekstury PBR, dodatki) |
| `export/weapon_ar15.fbx` | eksport FBX (hierarchia, UV, tekstury z `textures/`, właściwości) |
| `textures/*.png` | atlasy tekstur (broń 2048, dodatki 1024) |
| `renders/*.png` | rendery podglądowe (Cycles) |
| `blender/*.py` | generator — model jest w całości budowany skryptem, więc każdą poprawkę można odtworzyć |

## Wymiary (skala 1:1, 1 jednostka Blendera = 1 m)

| Parametr | Specyfikacja | Model |
|---|---|---|
| Długość całkowita, kolba złożona | 33" (838,2 mm) | **838,2 mm** |
| Długość całkowita, kolba rozłożona | 36,2" (919,4 mm) | **919,4 mm** (kolba przesuwa się o 81,2 mm, 6 pozycji) |
| Długość lufy (od czoła zamka do wylotu) | 16,1" (408,9 mm) | **408,9 mm** |
| Długość łoża | 15" (381 mm) | **381,0 mm** |
| Układ gazowy | carbine, DI | port gazowy 177,8 mm (7") od czoła zamka |
| Kaliber / skok gwintu | 5,56×45 mm NATO, 1:7 RH | przewód Ø 5,7 mm (właściwości na obiekcie głównym) |
| Szerokość / wysokość | — | 51 mm / 272 mm (z magazynkiem i przyrządami) |
| Masa | 3,0 kg | właściwość `mass_kg` na obiekcie `weapon_ar15` |

Proporcje sylwetki zostały zdjęte ze zdjęcia referencyjnego (skala 0,7945 mm/px, skalibrowana na
długość 33"), a render z boku pokrywa się ze zdjęciem 1:1.

## Układ współrzędnych

- **+X** w stronę wylotu lufy, **+Z** w górę, **+Y** lewa strona broni (okno wyrzutowe jest po stronie −Y).
- **Punkt (0, 0, 0)**: oś przewodu lufy × przednia płaszczyzna komory zamkowej górnej.
- Eksport GLB jest w konwencji glTF (+Y w górę); FBX zapisany z domyślnymi osiami Blendera.
  Orientację pod konkretny silnik ustawimy w kolejnym kroku.

## Dodatki

Wszystkie dodatki są generyczne (bez nazw i logo producentów) i siedzą w osobnych obiektach-rodzicach,
więc można je eksportować jako osobne komponenty broni:

| Obiekt | Dodatek | Mocowanie |
|---|---|---|
| `ar15_att_holo` | celownik holograficzny (szkło + podświetlany czerwony krzyż/pierścień) | szyna Picatinny komory górnej, `socket_att_scope` |
| `ar15_att_foregrip` | chwyt przedni pionowy | dolny slot M-LOK, `socket_att_grip` |
| `ar15_att_flashlight` | latarka taktyczna na montażu offset | prawy slot M-LOK, `socket_att_flashlight` |
| `ar15_att_laser` | moduł laserowy (laser + okno IR) | lewy slot M-LOK, `socket_att_laser` |

Przy założonym celowniku przyrządy mechaniczne są złożone jak w prawdziwej broni: tylny przeziernik
składa się do przodu (+90° wokół osi Y), muszka do tyłu (−90°) — obie mają pivot na osi zawiasu i
wnękę w podstawie, w którą chowają się po złożeniu. Punkty emisji: `socket_light_emit`, `socket_laser_emit`.

## Tekstury

Wypiekane (bake) atlasy PBR w `textures/`:

| Atlas | Rozdzielczość | Mapy |
|---|---|---|
| `ar15_weapon_*` | 2048 × 2048 | `basecolor` (z AO), `orm` (R = AO, G = roughness, B = metallic), `normal` (OpenGL) |
| `ar15_attachments_*` | 1024 × 1024 | jak wyżej |

Detal powierzchni: ziarno anodowanego aluminium, delikatne przetarcia krawędzi, faktura fosforanowanej
stali, stipple polimeru, radełkowanie chwytu, AO w zagłębieniach. Źródłowe materiały proceduralne
(`*__detail`) zostają w pliku .blend, więc bake można powtórzyć skryptem `blender/texture_bake.py`.

## Hierarchia i punkty obrotu (pod animacje)

```
weapon_ar15                       (empty, root)
└─ ar15_lower_receiver
   ├─ ar15_upper_receiver         pivot: przedni bolec (upper odchyla się jak w prawdziwej broni)
   │  ├─ ar15_bolt_carrier        suwadło z zamkiem, pivot na tyle (ruch po −X)
   │  ├─ ar15_charging_handle     rączka napinacza (ruch po −X)
   │  ├─ ar15_dust_cover          pokrywa okna wyrzutowego, pivot na osi zawiasu
   │  ├─ ar15_forward_assist
   │  ├─ ar15_rear_sight_base → ar15_rear_sight_leaf     pivot osi składania
   │  ├─ ar15_barrel → barrel_nut, gas_block, gas_tube, crush_washer, flash_hider
   │  └─ ar15_handguard → handguard_hardware, front_sight_base → front_sight_leaf
   ├─ ar15_trigger                pivot: oś spustu
   ├─ ar15_trigger_guard, ar15_selector (pivot: oś), ar15_mag_release, ar15_bolt_catch, ar15_pins
   ├─ ar15_pistol_grip
   ├─ ar15_buffer_tube → castle_nut, end_plate, stock → buttpad, stock_lever, stock_qd
   │                                   (stock: pivot z przodu kolby, przesuw 81,2 mm po −X)
   └─ ar15_magazine → magazine_lips, cartridge_case, cartridge_bullet
```

Sockety (empty) dla silnika: `socket_muzzle`, `socket_shell_eject`, `socket_grip`,
`socket_sight_rear`, `socket_sight_front`, `socket_magazine`, oraz dla dodatków
`socket_att_scope`, `socket_att_grip`, `socket_att_flashlight`, `socket_att_laser`,
`socket_light_emit`, `socket_laser_emit`.

## Siatka i materiały

- Broń ~114 tys. trójkątów (36 obiektów) + dodatki ~24 tys.; fazowane krawędzie + weighted normals.
- To jest model źródłowy (high-poly). Pod **FiveM / GTA V** zrobimy z niego wersję game-ready
  (niska siatka + bake normal map, tekstury, eksport `.ydr`) — po akceptacji kształtu.
- Materiały PBR: `ar15_aluminum_anodized`, `ar15_steel_phosphate`, `ar15_polymer`,
  `ar15_polymer_checkered` (radełkowanie chwytu jako proceduralny bump), `ar15_rubber`,
  `ar15_brass`, `ar15_copper`.

## Odtworzenie modelu

```bash
pip install bpy shapely          # Blender 5.0 jako moduł Pythona
python3 blender/build_weapon_ar15.py --save     # geometria + dodatki
python3 blender/texture_bake.py 2048            # atlasy UV + bake tekstur
python3 blender/export_all.py                   # GLB + FBX z teksturami
python3 blender/render_final.py 96              # rendery do renders/
```

lub w zainstalowanym Blenderze: `blender -b -P blender/build_weapon_ar15.py -- --save --export`.
