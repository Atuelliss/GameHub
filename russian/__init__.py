from .main import Russian

async def setup(bot):
    await bot.add_cog(Russian(bot))