# Russian Roulette Cog for Red-DiscordBot

A thrilling game of chance where users can bet credits or tokens on Russian Roulette games, either solo or by challenging other server members.

## Installation

To install this cog, run the following commands in your Red Discord Bot:


Replace `<repository-url>` with the URL to your GitHub repository.

## Setup

- We highly recommend you set a discord alias for [p]russian as "rr".
- Remember to decide if you want to use the Token system, or the Direct Redbot banking system, and set it appropriately before gameplay.
- Make sure you have the bank conversion on/off to your preference.
- Set whatever you allowed channels for the commands that you'd like, or leave it blank to permit them in all channels.

## Required Permissions

- **Manage Messages**: For optimal gameplay and cleaning up response messages

## Commands

### Player Commands
- **`[p]russian solo <amount>`**: Play a solo game, betting the specified amount
- **`[p]russian challenge <amount> <user1> <user2>`**: Challenge up to 2 users to a game with the specified bet
- **`[p]russianlb`** or **`[p]rrlb`**: View the Russian Roulette leaderboard
- **`[p]rrstats [@player]`**: View your stats or another player's stats
- **`[p]rrcommands`**: Display all commands you have access to

#### Token Conversion Commands (When Token Mode Enabled)
- **`[p]rrconvert token <amount>`**: Convert tokens to Discord credits
- **`[p]rrconvert discord <amount>`**: Convert Discord credits to tokens

### Admin Commands

#### Betting Settings
- **`[p]rrset minbet <amount>`**: Set the minimum bet amount (default: 100)
- **`[p]rrset maxbet <amount>`**: Set the maximum bet amount (default: 3000)
- **`[p]rrset default`**: Reset to default betting limits
- **`[p]rrset mode <direct|token>`**: Toggle between direct and token mode
- **`[p]rrset convert <on|off>`**: Enable or disable currency conversion

#### Channel Management
- **`[p]rrset channels [#channel1] [#channel2]`**: Set allowed channels
- **`[p]rrset listchannels`**: List all channels where Russian Roulette can be played

#### Player Data Management
- **`[p]rrset wipe @player`**: Wipe a player's statistics
- **`[p]rrset clearusers`**: Clear ALL user data (dangerous)

#### Information
- **`[p]rrset display`**: Show current Russian Roulette settings

## Game Modes

### Direct Mode (Default)
Uses Red's economy system directly. Players bet and win credits from the bot's economy.

### Token Mode
Uses a separate token-based economy. Players use tokens that are tracked separately from the bot's economy. Tokens can be converted to and from Discord credits when conversion is enabled.

## How to Play

### Solo Game
1. Use the `[p]russian solo <amount>` command to start a solo game
2. Click the 🔫 button to pull the trigger
3. If you survive, you can continue for higher rewards or cash out by hitting the X button
4. If you get the bullet, you lose your bet

### Challenge Game
1. Use the `[p]russian challenge <amount> <user1> <user2>` to challenge other players (up to 2 others)
2. The challenged players must accept within 30 seconds
3. Players take turns pulling the trigger
4. The last player standing wins the pot

## Stats Tracking

The cog tracks various statistics for each player:
- Wins
- Deaths
- Chickens (when a player cashes out)
- Challenges issued
- Challenges rejected
- Total games played
- Credits/tokens won/lost

## Leaderboard

View the server leaderboard with `[p]rrlb` to see:
- Top winners
- Most deaths
- Biggest chickens
- Most challenges
- Most rejections
- Most active players
- Biggest winners/losers

The leaderboard buttons will remain active for 3 minutes after the command is used.

## Channel Restrictions

By default, Russian Roulette can be played in any channel. Admins can restrict it to specific channels using the `[p]rrset channels [#channel]` command. If any channels are added to the allowed list, the game can ONLY be played in those channels.