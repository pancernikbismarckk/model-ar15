# weapon_styles — style trzymania broni (`/style`)

Zasób FiveM (OneSync) z animacjami trzymania broni **KTWR autorstwa Mr.KobraX**, przerobionymi
z paczek do GTA V / LSPDFR (instalacja przez OpenIV, jeden styl na całą grę) na zasób standalone,
w którym każdy gracz wybiera sobie styl w menu `/style`. Wybór zapisuje się u gracza i widzą go
inni gracze.

## Instalacja

1. Folder `weapon_styles` do `resources/` serwera, w `server.cfg`:

   ```
   ensure weapon_ar15        # jeśli masz AR-15 (przed weapon_styles)
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
| Karabin | karabiny, karabinki, PM-y, strzelby, AR-15 | Low Ready, Standard Low Ready, Position SUL, Relaxed Cradle, Sling Relaxed (każdy także w wariancie sprintu High Port / na pasie), High Port, Sling Down, Sling High — 18 |
| Pistolet | pistolety, rewolwery, Micro SMG, paralizator | Low Ready (+ bieg wysoko), Compressed Low Ready (+ bieg jedną ręką), Chest Ready (+ oburącz, + oburącz z niskim biegiem), Temple Index (+ bieg wysoko / nisko), Position SUL, Belt Relaxed — 12 |
| Karabin — skradanie | tryb skradania (Ctrl) z karabinem | Low Ready, High Ready |
| Pistolet — skradanie | tryb skradania z pistoletem | Compressed Ready, High Ready, Position SUL (+ chód Compressed), Compressed Ready (+ chód SUL), Calm Down! (2 warianty) |
| Bez broni — skradanie | skradanie bez broni | Holster Ready |
| Pistolet — osłona | za osłoną z pistoletem | Temple Index, Position SUL |

W każdej zakładce jest też **GTA** (animacje z gry), a w zakładce karabinów **AR-15 low ready**:
własne low ready z zasobu `weapon_ar15` (pozostałe karabiny zostają wtedy jak w GTA). To jest
domyślny wybór karabinu, więc bez otwierania menu AR-15 zachowuje się tak jak wcześniej.

## Jak to działa

- **Tryb natywny** — gra sama odtwarza styl (stanie, chód, bieg, sprint, obroty, przejścia do
  celowania), tak jak w KTWR. Każdy styl ma własny słownik animacji (`stream/ktwr_*.ycd`), zestaw
  klipów (`meta/clip_sets.xml`) postawiony przed zestawem broni z gry, zestaw animacji broni
  (`meta/weaponanimations.meta`, wpisy zmieniają tylko zestaw ruchu / osłony, reszta pól spada na
  zestaw z gry) i — dla skradania — tryb ruchu (`meta/pedpersonality.meta`). Skrypt przełącza je
  dla każdej postaci natywkami `SET_WEAPON_ANIMATION_OVERRIDE` i `SET_MOVEMENT_MODE_OVERRIDE`
  zależnie od broni w ręku (osłona, skradanie, kobieca postać freemode ma warianty `_F`).
- **Tryb skryptowy** — te same animacje grane na górnej części ciała (`TaskPlayAnim`: stanie,
  chód, bieg, sprint), synchronizowane do innych graczy przez grę. Celowanie, strzał,
  przeładowanie, pojazd, osłona, pierwsza osoba i animacje innych skryptów od razu go przerywają.
- `Config.Mode = 'auto'` (domyślnie): przy starcie skrypt sprawdza, czy gra przyjęła dodane
  zestawy klipów; jeśli tak — tryb natywny, jeśli nie — skryptowy. W konsoli F8 widać
  `[weapon_styles] native mode ...` albo `overlay mode ...`, a w nagłówku menu „Tryb natywny” /
  „Tryb skryptowy”. Można wymusić `'native'` albo `'overlay'`.
- Pierwsza osoba zawsze używa animacji z gry.

## Broń add-on

- **AR-15** (`WEAPON_AR15`, zasób `weapon_ar15`): ma wpisy we wszystkich zestawach karabinowych i
  trybach ruchu (z własnych plików meta AR-15), więc style działają natywnie. Gdy wybrany jest styl
  KTWR, low ready z `weapon_ar15` się wyłącza; przeładowanie z wypadającym magazynkiem działa z
  każdym stylem.
- **Glock 17** (`WEAPON_GLOCK17`): wpisy jak dla `WEAPON_PISTOL` we wszystkich zestawach
  pistoletowych, osłonowych i trybach skradania — style działają natywnie, a przy stylu GTA broń
  wraca do swoich własnych animacji. Jeśli Glock ma własny skrypt trzymania (low ready itp.) i ma
  go zachować, dopisz go do `Config.ExcludedWeapons`.
- **Każda inna broń add-on** dostaje styl swojej grupy (pistolet / karabin) w trybie skryptowym.
  Żeby działała natywnie, wygeneruj zasób z `--addon WEAPON_NAZWA=pistol:WEAPON_PISTOL` (albo
  `=rifle:WEAPON_CARBINERIFLE`).

## Synchronizacja (OneSync)

Wybór gracza (6 kategorii) idzie na serwer, który sprawdza nazwy stylów i wpisuje je do state baga
gracza `wstyles` (replikowany do wszystkich). Każdy klient nakłada style natywne na postacie
graczy w promieniu `Config.SyncDistance` (150 m); tryb skryptowy synchronizuje gra. Serwer
przyjmuje najwyżej jedną zmianę na 150 ms na gracza, ale ostatni wybór nigdy nie przepada.
Wybór zapisuje się w KVP klienta i wraca po ponownym wejściu. Export: `exports.weapon_styles:GetStyles()`.

## Ustawienia (`config.lua`)

| Opcja | Domyślnie | Opis |
|---|---|---|
| `Command` | `'style'` | komenda menu |
| `Mode` | `'auto'` | `'auto'`, `'native'`, `'overlay'` |
| `Defaults` | karabin `'ar15'`, reszta `'default'` | wybór gracza przed pierwszym otwarciem menu |
| `SyncDistance` | `150.0` | zasięg nakładania stylów innym graczom (tryb natywny) |
| `ExcludedWeapons` | `{}` | bronie, które zostają przy swoich animacjach, np. `{ 'WEAPON_GLOCK17' }` |
| `HiddenStyles` | `{}` | style ukryte w menu, np. `{ 'r17', 'p12' }` |

## Budowanie z paczek KTWR

```bash
pip install pillow
dotnet build tools/cwconv -c Release -o build/cwconv
git clone https://github.com/Hxrv3y/fivem-addon-weapon-tool-kit build/fivem-addon-weapon-tool-kit
python3 tools/weapon_styles/build_weapon_styles.py --packs <folder z paczkami KTWR .zip>
```

Potrzebne paczki: `01. KTWR BASE (Required)`, `Rifle (Movement) Pack`, `Pistol (Movement) Pack`,
`Pistol (Cover) Pack`. Generator zapisuje `stream/`, `meta/`, `shared/catalog.lua` i `html/img/`
(słowniki KTWR są kopiowane bez zmian, pod nowymi nazwami), a wynik jest powtarzalny.

## Co jest sprawdzone, a co wymaga testu w grze

- Sprawdzone tutaj: skrypty klienta i serwera przeszły symulowane scenariusze na zastępczych
  natywkach (tryb natywny i skryptowy, style innego gracza ze state baga, osłona, skradanie,
  pierwsza osoba, kobieca postać, Glock 17, inna broń add-on, reset po zatrzymaniu zasobu, limit
  zmian na serwerze); każda użyta natywka GTA istnieje w dokumentacji natywek (reszta to
  standardowe funkcje FiveM); menu wyrenderowane w Chromium; pliki meta powstają z wpisów z plików gry (KTWR BASE zawiera pełne pliki gry).
- Do sprawdzenia w grze (nie da się tu uruchomić GTA): czy build serwera przyjmuje dodane zestawy
  klipów (`CLIP_SETS_FILE`) — jeśli nie, zasób sam przechodzi w tryb skryptowy, więc style dalej
  działają, tylko na górnej części ciała.

## Autor animacji

Animacje i podglądy stylów: **KTWR — Mr.KobraX**. Zasób zawiera je bez zmian (inne są tylko nazwy
słowników), a autor jest podany w menu. Przed publikacją zasobu sprawdź warunki autora z jego
readme.
