import asyncio
import aiohttp
import gzip
import os
import xml.etree.ElementTree as ET

EPG_SOURCES = [
    "https://raw.githubusercontent.com/time2shine/IPTV/refs/heads/master/epg.xml"
]

OUTPUT_FILE = "FINAL_EPG_COMPLETE.xml.gz"

async def download_epg(session, url, index):
    filename = f"temp_epg_{index}.xml"
    try:
        print(f"Downloading {url}...")
        # Spoof user-agent to prevent blocks
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        async with session.get(url, headers=headers, timeout=60) as resp:
            if resp.status == 200:
                with open(filename, 'wb') as f:
                    while True:
                        chunk = await resp.content.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                print(f"[OK] Downloaded {url}")
                return filename
            else:
                print(f"[ERR] Failed to download {url} - Status: {resp.status}")
    except Exception as e:
        print(f"[FAIL] {url} - {e}")
    return None

async def main():
    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_epg(session, url, i) for i, url in enumerate(EPG_SOURCES)]
        files = await asyncio.gather(*tasks)

    valid_files = [f for f in files if f]
    
    if not valid_files:
        print("No EPG files downloaded. Exiting.")
        return

    print("Merging EPGs (this may take a minute for large files)...")
    seen_channels = set()
    
    with gzip.open(OUTPUT_FILE, 'wt', encoding='utf-8') as out_f:
        out_f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out_f.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">\n')
        out_f.write('<tv generator-info-name="Ultimate IPTV Pro EPG" generator-info-url="https://github.com/Zaman-Topu/Ip-tv-Collection">\n')

        # First pass: Write channels uniquely
        for file in valid_files:
            print(f"Extracting channels from {file}...")
            try:
                context = ET.iterparse(file, events=('end',))
                for event, elem in context:
                    if elem.tag == 'channel':
                        channel_id = elem.attrib.get('id')
                        if channel_id and channel_id not in seen_channels:
                            seen_channels.add(channel_id)
                            # Convert Element back to string and write
                            out_f.write(ET.tostring(elem, encoding='unicode'))
                        elem.clear() # Free memory
                    elif elem.tag == 'tv':
                        elem.clear()
            except Exception as e:
                print(f"Error parsing channels in {file}: {e}")

        # Second pass: Write programmes
        for file in valid_files:
            print(f"Extracting programmes from {file}...")
            try:
                context = ET.iterparse(file, events=('end',))
                for event, elem in context:
                    if elem.tag == 'programme':
                        channel_id = elem.attrib.get('channel')
                        # Only keep programmes for channels we included
                        if channel_id in seen_channels:
                            out_f.write(ET.tostring(elem, encoding='unicode'))
                        elem.clear()
                    elif elem.tag == 'tv':
                        elem.clear()
            except Exception as e:
                print(f"Error parsing programmes in {file}: {e}")

        out_f.write('</tv>\n')

    # Cleanup temp files
    for file in valid_files:
        try:
            os.remove(file)
        except:
            pass

    print(f"Success! Compressed EPG saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
