# highrollerclub/assets/

This folder holds the embed images for the High Roller Club cog.
Discord loads them from GitHub (`Atuelliss/GameHub`, branch `master`). The URLs are built in `common/constants.py` (`EMBED_IMAGES`).

## Adding an image

1. Make the image (PNG, see the sizes below). `game_thumbnail_prompts.MD` has a prompt for every image.
2. Save it in this folder under the exact filename in the table below.
3. Commit and push it to GameHub's `master` branch.

That's all. An image only switches on when its file is in this folder, so a game whose image isn't there yet shows no thumbnail instead of a broken one. No code changes are needed.

## Filenames

| Key | Filename | Status |
|---|---|---|
| `lobby` | `lobby_banner.png` | ✅ |
| `game_floor` | `game_floor_thumb.png` | ✅ |
| `teller` | `teller_thumb.png` | ✅ |
| `stats` | `stats_thumb.png` | ✅ |
| `leaderboard` | `leaderboard_thumb.png` | ✅ |
| `help` | `help_thumb.png` | ✅ |
| `slots` | `slots_thumb.png` | ✅ |
| `war` | `war_thumb.png` | ✅ |
| `allin` | `allin_thumb.png` | ✅ |
| `blackjack` | `blackjack_thumb.png` | missing |
| `hilo` | `hilo_thumb.png` | missing |
| `keno` | `keno_thumb.png` | missing |
| `roulette` | `roulette_thumb.png` | missing |
| `videopoker` | `video_poker_thumb.png` | missing |
| `clubpoker` | `club_poker_thumb.png` | missing |
| `big6` | `big_6_thumb.png` | missing |
| `mysteryspin` | `mystery_wheel_thumb.png` | missing |
| `multiplierwheel` | `multiplier_wheel_thumb.png` | missing |
| `double` | `double_thumb.png` | missing |
| `horserace` | `horse_racing_thumb.png` | missing |

## Image sizes

- **Thumbnails** (`set_thumbnail`): 256×256 or 512×512 px. Discord shows them at about 80 px wide.
- **Lobby banner** (`set_image`): 1024×512 px landscape, shown full-width at the bottom of the embed.
- Keep files under 500 KB. PNG or JPG both work.
