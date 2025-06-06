# Russian Roulette Cog for Red-DiscordBot

A thrilling game of chance where users can bet credits on Russian Roulette games, either solo or by challenging other server members.

## Installation

To install this cog, run the following commands in your Red Discord Bot:


Replace `<repository-url>` with the URL to your GitHub repository.

## Required Permissions

- **Manage Messages**: For optimal gameplay and cleaning up response messages

## Commands

### Player Commands
- **`[p]rr solo <amount>`**: Play a solo game, betting the specified amount
- **`[p]rr challenge <amount> <user1> <user2>`**: Challenge another user to a game with the specified bet
- **`[p]rrlb`**: View the Russian Roulette leaderboard

### Admin Commands
- **`[p]rrset minbet <amount>`**: Set the minimum bet amount (default: 100)
- **`[p]rrset maxbet <amount>`**: Set the maximum bet amount (default: 3000)
- **`[p]rrset channels <channel>`**: Add a channel to the allowed channels list
- **`[p]rrset listchannels`**: List all channels where Russian Roulette can be played



## How to Play

### Solo Game
1. Use the `[p]rr solo <amount>` command to start a solo game
2. Click the 🔫 button to pull the trigger
3. If you survive, you can continue for higher rewards or cash out by hitting teh X button
4. If you get the bullet, you lose your bet

### Challenge Game
1. Use the `[p]rr challenge <amount> <user1> <user2>` to challenge another player(upt to 2 others)
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
- Credits won/lost

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