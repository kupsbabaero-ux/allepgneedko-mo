# PH EPG Auto-Updater

Automatic daily (and mid-day) update of Philippine + selected international XMLTV EPG.

**Lahat ng sources naka-merge sa iisang `epg.xml`** — wala kang ireremove, lahat nandito:

- Bulk GitHub XMLs (`ph-tv-epg`, Cinema One CTC, Sony, etc.)
- `epg.pw` Philippines country guide
- Lahat ng individual epg.pw channels (Citytv, HBO variants, Sports, GMA intl, etc.) na Asia/Manila `+0800`

## How to use

1. Gumawa ng bagong **public** GitHub repository.
2. Upload / push ang laman ng folder na ito.
3. Actions tab → enable workflows.
4. Workflow `Update EPG Daily` tatakbo:
   - Automatic twice a day (00:15 & 12:15 Asia/Manila)
   - O i-click ang **Run workflow** anytime
5. Pagkatapos ng first successful run:

```
https://raw.githubusercontent.com/<your-username>/<your-repo>/main/epg/epg.xml
https://raw.githubusercontent.com/<your-username>/<your-repo>/main/epg/epg.xml.gz
```

Yun ang main URL na ilalagay mo sa player. May `.gz` din para mas mabilis.

## Files produced

| File | Description |
|------|-------------|
| **`epg.xml`** | **Main combined file** — lahat ng bulk + individual channels |
| `epg.xml.gz` | Gzipped version (recommended) |
| `ph-tv-epg.xml` | Mirror of networkrival PH guide |
| `epg_PH.xml` | Mirror of epg.pw Philippines bulk |
| `cinemaone-ctc.xml` | ClickTheCity multi (Cinema One / TV5 / A2Z / ANC) |
| `cinema_one_legacy.xml` | Older Cinema One PH |
| `sony-epg.xml` | Sony One / Movies / Cine |

Walang tinatanggal — individual mirrors nandiyan pa rin kung kailangan, pero **`epg.xml` na ang iisang source**.

## Customize

Edit `scripts/update_epg.py`:

- `BULK_SOURCES` — full XMLTV files to mirror + merge
- `EPG_PW_CHANNELS` — `channel_id → name` for individual epg.pw fetches

Push → next workflow run kukuha na.

## Local test

```bash
pip install requests
python scripts/update_epg.py
ls -lh epg/
```

## Notes

- Times forced to Asia/Manila (`+0800`) via epg.pw timezone parameter.
- Action only commits when content actually changes (hash check).
- Duplicate programmes (same channel + start + stop) are skipped once.
