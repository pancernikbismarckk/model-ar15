# weapon_styles — style trzymania broni (`/style`)

Zasób FiveM (OneSync) z animacjami trzymania broni **KTWR autorstwa Mr.KobraX**, przerobionymi
z paczek do GTA V / LSPDFR (instalacja przez OpenIV, jeden styl na całą grę) na zasób standalone,
w którym każdy gracz wybiera sobie styl w menu `/style`. Wybór zapisuje się u gracza i widzą go
inni gracze.

## Instalacja

1. Folder `weapon_styles` do `resources/` serwera, w `server.cfg`:

   ```
   ensure weapon_ar15        # jeśli masz AR-15
   ensure weapon_styles
   ```

   Wymagany OneSync (`set onesync on` albo OneSync „On” w txAdminie).
2. W grze: `/style`. Menu nie zabiera sterowania ruchem — można chodzić i biegać, żeby obejrzeć
   styl. ESC albo ✕ zamyka.

Gotowy zasób (z animacjami) jest w paczce z czatu. W repozytorium są tylko skrypty, menu i
generator; animacje, podglądy i wygenerowane pliki meta to materiały autora KTWR, więc powstają
z jego paczek (niżej: *Budowanie*).

## Style

| Zakładka | Dotyczy | Style |
|---|---|---|
| Karabin | karabiny, karabinki, PM-y, strzelby, AR-15 | Low Ready, Standard Low Ready, High Port, Position SUL, Relaxed Cradle, Sling Relaxed, Sling Down, Sling High — 8 |
| Pistolet | pistolety, rewolwery, Micro SMG, paralizator | Low Ready (+ bieg wysoko), Compressed Low Ready (+ bieg jedną ręką), Chest Ready (+ oburącz, + oburącz z niskim biegiem), Temple Index (+ bieg wysoko / nisko), Position SUL, Belt Relaxed — 12 |
| Karabin — skradanie | tryb skradania (Ctrl) z karabinem | Low Ready, High Ready |
| Pistolet — skradanie | tryb skradania z pistoletem | Compressed Ready, High Ready, Position SUL (+ chód Compressed), Compressed Ready (+ chód SUL), Calm Down! (2 warianty) |
| Bez broni — skradanie | skradanie bez broni | Holster Ready |
| Pistolet — osłona | za osłoną z pistoletem | Temple Index, Position SUL |

W każdej zakładce jest też **GTA** (animacje z gry) — to wybór domyślny. Karty „AR-15 low ready”
od 1.6 nie ma; kto miał ją wybraną, dostaje GTA.

## Jak to działa

- **Tryb natywny** — karabin i pistolet: gra sama odtwarza styl (stanie, chód, bieg, obroty,
  przejścia do celowania), tak jak w KTWR. Każdy styl ma własny słownik animacji
  (`stream/ktwr_*.ycd`) i zestawy klipów (`meta/clip_sets.xml`), w których ten słownik stoi przed
  łańcuchem klipów, jaki KTWR BASE daje danej broni (np. `ktwr_r08@weapons@rifle@hi@assault_rifle`).
  Skrypt zakłada go na postać natywką `SET_PED_WEAPON_MOVEMENT_CLIPSET` (zestaw ruchu z bronią),
  a gra sama wysyła go innym graczom (węzeł synchronizacji ruchu postaci). Styl osłony z pistoletem
  idzie przez `SET_PED_MOTION_IN_COVER_CLIPSET_OVERRIDE` i nie jest synchronizowany przez grę, więc
  każdy klient zakłada go graczom w pobliżu. Style skradania są nakładką (niżej).
- **Sprint z karabinem** (Shift): gra zawsze gra własny sprint z karabinem, niezależnie od zestawu
  klipów stylu, a style KTWR mają dokładnie ten sam sprint. Styl zostaje więc na postaci także w
  sprincie, a przejścia bieg ↔ sprint robi sama gra. Paczka karabinów KTWR ma jeszcze warianty
  „+ High Port Sprint” / „+ Sling Sprint” (ten sam styl z innym sprintem) — tu ich nie ma: gra i
  tak by ich sprintu nie zagrała, a dogrywanie go skryptem (1.3, 1.4) dawało skoki i dziwne ręce.
  Kto miał taki wariant zapisany, dostaje jego styl bazowy.
- **Nakładka** — animacje stylu na górnej części ciała (`TaskPlayAnim`: stanie, chód, bieg,
  sprint), synchronizowane przez grę. Tak działają style skradania, a w **trybie skryptowym**
  wszystkie style. Celowanie, strzał, przeładowanie, pojazd, osłona, pierwsza osoba i animacje
  innych skryptów od razu ją przerywają.
- `Config.Mode = 'auto'` (domyślnie): przy starcie skrypt sprawdza, czy gra przyjęła dodane
  zestawy klipów; jeśli tak — tryb natywny, jeśli nie — skryptowy (bez stylów osłony). W konsoli F8
  widać `[weapon_styles] native mode ...` albo `overlay mode ...`, a w nagłówku menu „Tryb
  natywny” / „Tryb skryptowy”. Można wymusić `'native'` albo `'overlay'`.
- Pierwsza osoba zawsze używa animacji z gry.
- Skrypt cofa tylko to, co sam ustawił, więc zestawy klipów zakładane przez inne skrypty (noszenie
  pudła, kanistra itp.) zostają.
- Wersja 1.0 używała własnych zestawów animacji broni (`weaponanimations.meta`) i trybów ruchu
  (`pedpersonality.meta`) — gra ich nie tworzy z plików zasobu (jej DLC tylko dopisują bronie do
  istniejących zestawów), przez co broń wisiała w dłoni bez animacji. Od 1.1 ich nie ma.

## Broń add-on

- Każda broń z grup pistolet / karabin (także add-on) dostaje styl natywnie: bronie z gry i
  **AR-15** (`WEAPON_AR15`, łańcuch jak Carbine Rifle) oraz **Glock 17** (`WEAPON_GLOCK17`,
  łańcuch jak Pistol) mają własne wpisy, pozostałe dostają łańcuch Carbine Rifle / Pistol.
- AR-15: przy działającym `weapon_styles` trzyma się jak wybrany styl karabinu (albo jak w GTA),
  a własne low ready z `weapon_ar15` jest wyłączone; przeładowanie z wypadającym magazynkiem
  działa z każdym stylem.
- Jeśli jakaś broń ma własny skrypt trzymania i ma go zachować, dopisz ją do
  `Config.ExcludedWeapons`.

## Synchronizacja (OneSync)

Wybór gracza (6 kategorii) idzie na serwer, który sprawdza nazwy stylów i wpisuje je do state baga
gracza `wstyles` (replikowany do wszystkich). Styl karabinu / pistoletu i nakładkę synchronizuje
gra; klienci z state baga ładują zestawy klipów graczy w promieniu `Config.SyncDistance` (150 m)
i zakładają im styl osłony. Serwer przyjmuje najwyżej jedną zmianę na 150 ms na gracza, ale
ostatni wybór nigdy nie przepada. Wybór zapisuje się w KVP klienta i wraca po ponownym wejściu.
Export: `exports.weapon_styles:GetStyles()`.

## Ustawienia (`config.lua`)

| Opcja | Domyślnie | Opis |
|---|---|---|
| `Command` | `'style'` | komenda menu |
| `Mode` | `'auto'` | `'auto'`, `'native'`, `'overlay'` |
| `Defaults` | wszędzie `'default'` (GTA) | wybór gracza przed pierwszym otwarciem menu |
| `SyncDistance` | `150.0` | zasięg, w którym klient ładuje style innych graczy (tryb natywny) |
| `ExcludedWeapons` | `{}` | bronie, które zostają przy swoich animacjach, np. `{ 'WEAPON_GLOCK17' }` |
| `HiddenStyles` | `{}` | style ukryte w menu, np. `{ 'r17', 'p12' }` |

## Budowanie z paczek KTWR

```bash
pip install pillow
python3 tools/weapon_styles/build_weapon_styles.py --packs <folder z paczkami KTWR .zip>
```

Potrzebne paczki: `01. KTWR BASE (Required)`, `Rifle (Movement) Pack`, `Pistol (Movement) Pack`,
`Pistol (Cover) Pack`. Generator zapisuje `stream/`, `meta/clip_sets.xml`, `shared/catalog.lua` i
`html/img/` (słowniki KTWR pod nowymi nazwami, z nowymi sygnaturami animacji — niżej), a wynik jest
powtarzalny; na końcu sprawdza, że żadna sygnatura się nie powtarza.
Kolejna broń add-on z własnym łańcuchem: `--addon WEAPON_NAZWA=rifle:WEAPON_CARBINERIFLE`.

## Co jest sprawdzone, a co wymaga testu w grze

- Z nagrania z gry (wersja 1.0): menu, zapis wyboru i wykrycie trybu działały, a style KTWR nie —
  broń wisiała w dłoni, bo gra nie utworzyła własnych zestawów animacji broni. Poprawione w 1.1.
- Ze zrzutu crasha (wersja 1.1, zmiana stylu pistoletu, `GTA5_b3258.exe+137D04A`): gra padała w
  wątku animacji przy składaniu klatki — zapisywała dane ścieżek pod złe adresy. Przyczyna: każda
  animacja ma sygnaturę, pod którą gra trzyma w pamięci podręcznej mapę „ścieżki animacji → kości
  postaci”. Style KTWR to przeróbki tych samych animacji z gry i zostawiły ich sygnatury, choć mają
  inne ścieżki (np. jedna sygnatura przy 8 różnych układach w stylach pistoletu). W singlu KTWR
  działa, bo naraz jest tylko jeden styl; tu po zmianie stylu gra brała mapę od poprzedniego.
  Od 1.2 każda animacja i sekwencja ma własną sygnaturę (`cwconv ycdsig`: zmienione są tylko te
  pola, reszta plików bajt w bajt jak u autora). Animacje AR-15 też (Sollumz liczy sygnaturę z
  nazwy animacji, np. `reload`, a takie nazwy mają też inne zasoby).
- Z nagrań z gry (1.3 i 1.4): w sprincie z wariantem sprintu lewa dłoń wisiała przed klatką — to
  lewa ręka ze sprintu gry, który gra puszcza niezależnie od stylu; 1.4 do tego zdejmowała styl na
  czas sprintu, a gra zmienia zestaw klipów bez przejścia, więc postać przeskakiwała między pozami.
  Od 1.5 styl zostaje w sprincie, od 1.6 wariantów sprintu nie ma.
- Sprawdzone tutaj: skrypty klienta i serwera przeszły symulowane scenariusze na zastępczych
  natywkach (zestaw klipów tylko po załadowaniu i tylko zdefiniowany w `clip_sets.xml`, ponowne
  założenie po zmianie broni, pojeździe i śmierci, osłona, skradanie, pierwsza osoba, kobieca
  postać, Glock 17, inna broń add-on, inni gracze, reset po zatrzymaniu zasobu, limit zmian na
  serwerze); każda użyta natywka GTA istnieje w dokumentacji natywek (reszta to standardowe funkcje
  FiveM); to, że gra synchronizuje zestaw ruchu z bronią, wynika z kodu OneSync FiveM
  (`CPedMovementGroupDataNode`); menu wyrenderowane w Chromium.
- Do sprawdzenia w grze (nie da się tu uruchomić GTA): wygląd stylów na postaci i u innych graczy
  oraz styl osłony. Gdyby tryb natywny dalej wyglądał źle, `Config.Mode = 'overlay'` gra style
  samym skryptem.

## Autor animacji

Animacje i podglądy stylów: **KTWR — Mr.KobraX**. Zasób zawiera je bez zmian (inne są tylko nazwy
słowników), a autor jest podany w menu. Przed publikacją zasobu sprawdź warunki autora z jego
readme.
