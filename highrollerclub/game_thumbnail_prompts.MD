# HighRollerClub — Embed Image Generation Prompts

All images generated using **Bing Image Creator (DALL-E 3)** — free with a Microsoft account.
Generated assets are stored in `highrollerclub/assets/` and served via raw GitHub URLs.
See `assets/README.md` for the full activation workflow.

**Style anchor used across all prompts:** `photorealistic art deco luxury casino`
This phrase appears in every prompt to maintain a consistent visual identity across all 18 images.

---

## Main Lobby — `lobby`

**Discord method:** `.set_image()` — large landscape banner at the bottom of the embed
**Target size:** 1024×512 px (landscape — requires cropping after generation)
**Composition note:** `wide landscape composition, cinematic aspect ratio`

> Exterior entrance of an ultra-luxury art deco casino at night, grand arched doorway with gold trim and deep black marble, warm amber and gold neon glow emanating from inside, red velvet rope in foreground, dramatic cinematic lighting, no people, no text, photorealistic art deco luxury casino, wide landscape composition, cinematic aspect ratio

---

## Navigation Views

All navigation view images use `.set_thumbnail()` — small square image in the top-right corner of the embed.
**Target size:** 512×512 px (square — Bing Image Creator outputs square by default)
**Composition note appended to all:** `square composition, centered subject, no wide margins`

---

### Game Floor — `game_floor`
*Triggered by: 🎲 Game Room button*

> Aerial view of a high-end casino game floor, green felt tables with gold trim arranged symmetrically, stacks of gold and black casino chips, dramatic overhead chandeliers casting warm golden light, dark atmosphere, no people, no text, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Teller Window — `teller`
*Triggered by: 🏦 Teller Window button (chip mode only)*

> A polished dark marble casino teller window, an ornate gold grate, stacks of casino chips in black and gold arranged neatly in front, warm spotlight lighting from above, no people, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Stats View — `stats`
*Triggered by: 📊 Your Stats button*

> A single oversized gold playing card with a blank dark face, resting on black velvet beside a small gleaming gold trophy, dramatic single spotlight from above, rich shadows, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Leaderboards — `leaderboard`
*Triggered by: 🏆 Leaderboards button*

> Three tiered podium platforms in polished black marble trimmed with gold, first place platform tallest with a golden glow, second and third in silver and bronze glow, dramatic stage lighting from above, empty platforms, no people, no text, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Help & Info — `help`
*Triggered by: ❓ Help & Info button*

> An open leather-bound book with blank pages resting on a dark casino felt table, ornate gold page edges, a brass magnifying glass beside it, warm candlelight illumination, no text on pages, no people, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

## Games

All game images use `.set_thumbnail()` — small square image in the top-right corner of the embed.
**Target size:** 512×512 px
**Composition note appended to all:** `square composition, centered subject, no wide margins`

---

### Slots — `slots`
*The Main Floor*

> Close-up of a vintage luxury slot machine, three reels showing gold bar symbols, chrome and black cabinet with gold accents, buttons glowing amber, dramatic side lighting, no people, no text, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### War — `war`
*The Entry Table*

> Two playing cards face-down on dark green casino felt, gold card backs with an ornate pattern, one card slightly lifted at the corner as if about to be flipped, dramatic tension lighting, no people, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### All-In — `allin`
*The High Stakes Toss*

> A large dramatic pile of black and gold casino chips pushed dramatically toward the center of a dark green felt table, motion blur on chips, overhead spotlight, high stakes tension atmosphere, no people, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Blackjack — `blackjack`
*The 21 Lounge*

> Two face-up playing cards showing an ace and a king on dark green casino felt, a neatly stacked pile of gold and black chips beside them, subtle overhead warm lighting, no people, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Hi-Lo — `hilo`
*The Prediction Parlor*

> A single oversized playing card face-up revealing the seven of hearts on dark green felt, half the card dramatically lit, the other half in deep shadow suggesting anticipation, no people, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Keno — `keno`
*The Numbers Room*

> A cluster of glossy numbered lottery balls in gold and black, scattered across a dark velvet surface, dramatic rim lighting giving each ball a metallic sheen, numbers clearly visible on balls, no people, no additional text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Roulette — `roulette`
*The Grand Wheel*

> Close-up of a spinning roulette wheel in dark mahogany and gold, the ball mid-spin caught in motion blur along the outer track, black and red number slots gleaming, dramatic overhead spotlight, no people, no text, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Video Poker — `videopoker`
*The Private Card Room*

> A fan of five playing cards spread face-up on dark green felt, cards showing a royal flush in spades, gold and black casino chips stacked neatly beside them, warm overhead glow, no people, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Club Poker — `clubpoker`
*The High Table*

> Aerial top-down view of a circular poker table with dark green felt, chips piled in the center pot from multiple players' positions, playing cards face-down at each position, dramatic overhead chandelier lighting, no people, no text, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Big Six Wheel — `big6`

> A large vertical money wheel mounted in gold and black, ornate dollar sign segments glowing under warm spotlights, the wheel at rest showing a $20 segment at the top, dark background, no people, no text, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Mystery Wheel — `mysteryspin`
*Daily Free Spin*

> A glowing prize wheel in darkness, its segment labels obscured by golden mist and soft bokeh, an ethereal aurora-like glow pulsing from the center, mysterious and dramatic atmosphere, no people, no text, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Multiplier Wheel — `multiplierwheel`
*The Booster*

> A prize wheel with glowing neon gold segments labeled with multiplier numbers like 1.5x and 3x, spinning with motion blur on outer edges, dramatic dark background with rim lighting in amber and gold, no people, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

### Double — `double`
*Double or Nothing*

> A single large gold coin suspended mid-spin in the air above a dark green casino felt surface, motion blur on its edges capturing the rotation, three progressively taller stacks of black and gold casino chips arranged behind it suggesting escalating stakes, dramatic single overhead spotlight illuminating the coin, deep shadows, high tension atmosphere, no people, no text, close-up, photorealistic art deco luxury casino, square composition, centered subject, no wide margins

---

## Generation Tips

- Generate 4 variants per prompt and pick the best result.
- If unwanted text appears rendered in the image, append `no lettering, no words` to the prompt and regenerate.
- The lobby banner is the **only** image requiring post-generation cropping to 1024×512. All others output naturally square from Bing Image Creator.
- Keep exported file sizes under 500 KB. PNG is preferred over JPG for thumbnails.
- Name files to match the key in `EMBED_IMAGES` in `common/constants.py` (e.g. `slots.png`, `lobby_banner.png`).
