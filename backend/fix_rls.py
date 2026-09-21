import asyncio
import asyncpg
from app.config import settings

async def main():
    pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
    async with pool.acquire() as conn:
        print("Dropping old policy...")
        await conn.execute('DROP POLICY IF EXISTS "own_data" ON public.message_threads;')
        print("Creating new optimized policy...")
        await conn.execute('''
            CREATE POLICY "own_data" ON public.message_threads FOR ALL USING (
                EXISTS (SELECT 1 FROM public.messages WHERE id = message_id AND user_id = current_setting('app.user_id', true))
            );
        ''')
        print("Policy updated successfully!")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
