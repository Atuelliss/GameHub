# highrollerclub/assets/

This folder holds all static image assets for the HighRollerClub cog.
Images are served via raw GitHub URLs and referenced in `common/constants.py` under `EMBED_IMAGES`.

## Usage

1. Download or generate your image file (PNG recommended, 512×512 or 1024×512 for the lobby banner).
2. Drop it into this folder.
3. Commit and push to GitHub.
4. Copy the raw URL: `https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/highrollerclub/assets/<filename.png>`
5. Paste it into the corresponding entry in `EMBED_IMAGES` in `common/constants.py`.
6. Uncomment the `embed_image(...)` snippet in the relevant view's embed build block.

## File Naming Convention

| Key | Suggested filename |
|---|---|
| `lobby` | `lobby_banner.png` |
| `game_floor` | `game_floor.png` |
| `teller` | `teller.png` |
| `stats` | `stats.png` |
| `leaderboard` | `leaderboard.png` |
| `help` | `help.png` |
| `slots` | `slots.png` |
| `war` | `war.png` |
| `allin` | `allin.png` |
| `blackjack` | `blackjack.png` |
| `hilo` | `hilo.png` |
| `keno` | `keno.png` |
| `roulette` | `roulette.png` |
| `videopoker` | `videopoker.png` |
| `clubpoker` | `clubpoker.png` |
| `big6` | `big6.png` |
| `mysteryspin` | `mysteryspin.png` |
| `multiplierwheel` | `multiplierwheel.png` |

## Image Size Guidelines

- **Thumbnails** (`set_thumbnail`): 256×256 or 512×512 px — Discord scales them down to ~80px display width.
- **Lobby banner** (`set_image`): 1024×512 px wide landscape — displayed full-width at the bottom of the embed.
- Keep file sizes under 500 KB. PNG or JPG both work.
