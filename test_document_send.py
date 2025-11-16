# -*- coding: utf-8 -*-
"""
Testovyi script dlya proverki otpravki dokumentov po file_id
"""
import asyncio
import sys
from aiogram import Bot
from app.config import settings

# Fix console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

async def test_send_documents():
    bot = Bot(token=settings.BOT_TOKEN)

    # Vash Telegram ID dlya testa
    test_user_id = settings.ADMIN_ID

    print(f"Otpravka testovykh dokumentov polzovatelyu {test_user_id}")
    print(f"DOC_OFERTA_FILE_ID: {settings.DOC_OFERTA_FILE_ID}")
    print(f"DOC_PRIVACY_FILE_ID: {settings.DOC_PRIVACY_FILE_ID}")
    print(f"DOC_USER_AGREEMENT_FILE_ID: {settings.DOC_USER_AGREEMENT_FILE_ID}")
    print(f"DOC_PERSONAL_DATA_FILE_ID: {settings.DOC_PERSONAL_DATA_FILE_ID}")

    try:
        # Dokument 1: Oferta
        print("\nOtpravka dokumenta 1: Oferta...")
        await bot.send_document(
            chat_id=test_user_id,
            document=settings.DOC_OFERTA_FILE_ID,
            caption="Test - Dokument 1: Oferta",
            parse_mode="HTML"
        )
        print("OK: Dokument 1 otpravlen uspeshno!")

        # Dokument 2: Politika konfidentsialnosti
        print("\nOtpravka dokumenta 2: Politika konfidentsialnosti...")
        await bot.send_document(
            chat_id=test_user_id,
            document=settings.DOC_PRIVACY_FILE_ID,
            caption="Test - Dokument 2: Politika konfidentsialnosti",
            parse_mode="HTML"
        )
        print("OK: Dokument 2 otpravlen uspeshno!")

        # Dokument 3: Polzovatelskoe soglashenie
        print("\nOtpravka dokumenta 3: Polzovatelskoe soglashenie...")
        await bot.send_document(
            chat_id=test_user_id,
            document=settings.DOC_USER_AGREEMENT_FILE_ID,
            caption="Test - Dokument 3: Polzovatelskoe soglashenie",
            parse_mode="HTML"
        )
        print("OK: Dokument 3 otpravlen uspeshno!")

        # Dokument 4: Soglasie na obrabotku personalnykh dannykh
        print("\nOtpravka dokumenta 4: Soglasie na obrabotku personalnykh dannykh...")
        await bot.send_document(
            chat_id=test_user_id,
            document=settings.DOC_PERSONAL_DATA_FILE_ID,
            caption="Test - Dokument 4: Soglasie na obrabotku personalnykh dannykh",
            parse_mode="HTML"
        )
        print("OK: Dokument 4 otpravlen uspeshno!")

        print("\nVse dokumenty otpravleny uspeshno!")

    except Exception as e:
        print(f"\nOSHIBKA otpravki dokumentov: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await bot.session.close()

if __name__ == "__main__":
    print("Zapusk testovoi otpravki dokumentov...")
    asyncio.run(test_send_documents())
