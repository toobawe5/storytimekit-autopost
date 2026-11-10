# StorytimeKit Autopost

Free daily product videos for the StorytimeKit Etsy shop. GitHub runs this every hour.
At each posting time in `config/schedule.json` it takes the next post from
`content/queue.json`, makes a 30-second vertical video from the product's images,
and posts it to Instagram Reels, Facebook Reels and YouTube Shorts (Pinterest once approved).
Every video also lands on a **Release** page so you can download it on your phone for TikTok.

Cost: $0. Everything runs on GitHub's free plan and the platforms' own free APIs.

---

## How a day works

| What | Who |
|---|---|
| New Etsy listings → send the links to Claude once a week; Claude adds the posts to `content/queue.json` | You + Claude |
| At each slot time, a video is made (and posted, once live mode is on) | GitHub, automatic |
| TikTok: open the repo's **Releases** page on your phone → download `video.mp4` → upload in TikTok, paste the caption shown there | You, ~2 min |

**Review mode (start here).** While the repo variable `POST_MODE` is `review`, videos are made but **not posted**.
Check each one on the Releases page. If it's good: **Actions → Daily post → Run workflow**,
type the post id, choose `live`, Run. Switch `POST_MODE` to `live` when you trust it.

---

## One-time setup

Never paste keys or tokens into a chat, an issue or a file. They only go into
**Settings → Secrets and variables → Actions**.

### 1. Repo settings (2 minutes)

1. **Settings → Actions → General → Workflow permissions** → choose **Read and write permissions** → Save.
2. **Settings → Secrets and variables → Actions → Variables tab → New repository variable**:
   - `POST_MODE` = `review`
   - `PLATFORMS` = `instagram,facebook,youtube`
3. **Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/docs` → Save.
   Your privacy policy page (Meta asks for one) will be at
   `https://toobawe5.github.io/storytimekit-autopost/privacy.html`.

### 2. Instagram + Facebook (about 30 minutes)

Before you start: Instagram must be a **Professional (Creator or Business)** account and
**linked to your StorytimeKit Facebook Page**.

1. Go to <https://developers.facebook.com> → log in → **My Apps → Create App**.
   Name it `StorytimeKit Autopost`. When asked for use cases, pick the ones for
   **managing a Facebook Page** and **Instagram (API setup with Facebook login)**.
2. **App settings → Basic** → *Privacy Policy URL* = the privacy page from step 1.3 → Save.
   Then switch **App Mode** to **Live** (top of the page).
3. Open **Tools → Graph API Explorer**. Pick your app. Under *Permissions* add:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   `instagram_basic`, `instagram_content_publish`, `business_management`.
   Click **Generate Access Token** and approve everything for your Page and Instagram.
4. Click the blue **i** next to the token → **Open in Access Token Tool** →
   **Extend Access Token** → copy the long-lived token it shows.
5. Back in Graph API Explorer, paste that long-lived token, type `me/accounts` in the box, press **Submit**.
   Find StorytimeKit in the result and copy:
   - its `access_token` → save as secret **`META_PAGE_TOKEN`**
   - its `id` → save as secret **`META_PAGE_ID`**
6. In Explorer, paste the page token, and query `<your page id>?fields=instagram_business_account`.
   Copy the id inside `instagram_business_account` → secret **`IG_USER_ID`**.
7. Check: paste the page token into <https://developers.facebook.com/tools/debug/accesstoken/>.
   It should say **Expires: Never**.

### 3. YouTube (about 20 minutes)

1. <https://console.cloud.google.com> → create a project `storytimekit-autopost`.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen** → External → fill the app name and your email.
   Under *Audience*, click **Publish app** so it's **In production**.
   (If you leave it in *Testing*, the login stops working every 7 days.)
4. **Credentials → Create credentials → OAuth client ID** → type **Web application** →
   add the redirect URI `https://developers.google.com/oauthplayground` → Create.
   Save the **Client ID** as secret **`YT_CLIENT_ID`** and the **Client secret** as **`YT_CLIENT_SECRET`**.
5. Open <https://developers.google.com/oauthplayground> → gear icon → tick **Use your own OAuth credentials**
   → paste the client ID and secret. In the left box type
   `https://www.googleapis.com/auth/youtube.upload` → **Authorize APIs** → log in with the
   YouTube channel's account (click *Advanced → continue* on the "unverified app" warning; it's your own app).
   Then **Exchange authorization code for tokens** → copy the **Refresh token** → secret **`YT_REFRESH_TOKEN`**.
6. **Heads-up:** Google keeps uploads from a new, unaudited API project **private** until the project passes its free
   audit. Apply here: <https://support.google.com/youtube/contact/yt_api_form>. Until approved, open YouTube Studio
   and switch each Short to Public by hand (10 seconds each).
7. Verify the channel by phone (<https://www.youtube.com/verify>) so custom thumbnails are allowed.

### 4. Pinterest (later)

Apply for **Standard access** at <https://developers.pinterest.com> (needs a short screen-recording demo).
Pins made before approval are only visible to you, so leave Pinterest out of `PLATFORMS` until you're approved.
Then add secrets `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`, `PINTEREST_REFRESH_TOKEN`,
put each product's board id in `products.json` (`pinterest_board_id`), and add `pinterest` to `PLATFORMS`.

### 5. Test it

**Actions → Daily post → Run workflow** → leave *item* empty or type a post id → mode `review` → Run.
After ~3 minutes the video appears under **Releases**.

---

## Adding a product

1. In the repo: **Add file → Upload files**. Drag in 3–6 images from Canva (cover first, then inside pages,
   then a mockup). In the file name box at the top, put them in a folder named after the product, e.g.
   `products/calm-down-corner/01.png`. Images are used in name order.
2. Add the product to `products/products.json`:

```json
{
  "id": "calm-down-corner",
  "name": "Feelings & Calm Down Corner Printable Kit",
  "etsy_url": "https://www.etsy.com/listing/1234567890",
  "pinterest_board_id": ""
}
```

## A post in `content/queue.json`

Leave `date` and `slot` as `null` and posts go out in order, one per slot.
Set them (`"2026-11-20"`, `"first"`) to pin a post to a specific day.

```json
{
  "id": "calm-down-corner-1",
  "product": "calm-down-corner",
  "date": null,
  "slot": null,
  "hook": "Big feelings, tiny humans?",
  "captions": ["Big feelings, tiny humans?", "A calm-down corner in minutes", "Feelings cards they can point to", "Breathing pages to reset", "Print at home tonight"],
  "caption": "Main caption used for Instagram, Facebook and TikTok. Link in bio.",
  "hashtags": "#toddlermom #calmdowncorner #printables",
  "youtube": {"title": "Calm down corner for toddlers #shorts", "description": "…", "tags": ["calm down corner"]},
  "pinterest": {"title": "Toddler Calm Down Corner Printable Kit", "description": "…"}
}
```

Optional per-platform text: add `"instagram"`, `"facebook"` or `"tiktok"` with its own caption.

## Changing posting times

Edit `config/schedule.json` (Pakistan time). Add or remove slots freely:

```json
{ "timezone": "Asia/Karachi", "late_limit_hours": 3, "slots": { "first": "06:00", "second": "18:00" } }
```

GitHub's timer can run 5–30 minutes late, so posts go out shortly after the time you set.

## Music

Add a royalty-free track as `assets/music.mp3` (you must have the rights). Without it, videos have a silent track.

## If something fails

GitHub emails you when a run fails. Open **Actions → the red run → "Make video and post"** to read the error.
`data/posted.json` records what went out where. Re-running a post only retries the platforms that failed.
