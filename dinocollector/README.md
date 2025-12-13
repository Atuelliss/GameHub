# Setting up the cog's features

As the Server Owner, you can choose to do this manually(run [p]dccommands to see all the commands) or you can use the guided setup which comes in both a Quick and a Full version. You can start this by sending the [p]dcsetup command and it will ask you which of the two you want to use. Quick sets just the most basic features and leaves the rest default, while Full allows you total customization of the games implementation in your server. The `[p]dcset display` command lists all the most common features you can access directly.

## Advanced Cookiecutter

This cog template is a more advanced version of the simple cog template. It includes a more robust structure for larger cogs, and utilizes Pydantic to objectify config data so that youre not messing around with dictionaries all the time. It also uses its own file store instead of Red's config.

### Key Components

- Subclassed commands, listeners, and tasks
- Pydantic "database" management
- Conservative i/o writes to disk
- Non blocking `self.save()` method

#### Credit of Intellectual Property

This is a discord game taking inspiration from the "Ark:Survival Evolved and Survival Ascended" games. Wildcard is the sole owner and holder of Copyrights for that game. This discord game, Dino Collector, is made with the intention of free-use among a community and not for-profit. As such, usage of said intellectual property(Ark) as inspiration is done so under the Fair Use copyright limitation. All creative additions and programming of this game belongs to Jayar(Vainne) and may not be used by others in a for-profit manner.