import os
import time
import json
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

API = f"https://tapi.bale.ai/bot{BOT_TOKEN}"


def main():
    offset = 0

    print(
        "=== SALAR DEBUG BOT STARTED ===",
        flush=True
    )

    while True:
        try:
            response = requests.post(
                f"{API}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": 15
                },
                timeout=25
            )

            data = response.json()

            if not data.get("ok"):
                print(
                    "BALE API ERROR:",
                    json.dumps(
                        data,
                        ensure_ascii=False
                    ),
                    flush=True
                )

                time.sleep(3)
                continue

            updates = data.get("result", [])

            for update in updates:

                update_id = update.get("update_id")

                if update_id is not None:
                    offset = update_id + 1

                print(
                    "\n========== NEW UPDATE ==========",
                    flush=True
                )

                print(
                    json.dumps(
                        update,
                        ensure_ascii=False,
                        indent=2
                    ),
                    flush=True
                )

                print(
                    "========== END UPDATE ==========\n",
                    flush=True
                )

        except requests.exceptions.ReadTimeout:
            # برای Long Polling طبیعی است.
            # دوباره درخواست بعدی را می‌فرستیم.
            continue

        except requests.exceptions.RequestException as e:
            print(
                "NETWORK ERROR:",
                repr(e),
                flush=True
            )

            time.sleep(3)

        except Exception as e:
            print(
                "ERROR:",
                repr(e),
                flush=True
            )

            time.sleep(3)


if __name__ == "__main__":
    main()
