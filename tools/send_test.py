"""Send one local single-player development Lua file and wait for its acknowledgement."""
from pathlib import Path
import sys,time,json
data=Path(r'E:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\data\microduck_dev')
data.mkdir(exist_ok=True)
ack=data/'ack.txt'
if ack.exists(): ack.unlink()
(data/'command.txt').write_text(Path(sys.argv[1]).read_text(encoding='utf-8'),encoding='utf-8')
end=time.monotonic()+20
while time.monotonic()<end:
    if ack.exists():
        result=json.loads(ack.read_text()); print(json.dumps(result)); sys.exit(0 if result.get('ok') else 1)
    time.sleep(.1)
raise TimeoutError('Game did not acknowledge test command; check that local test transport is loaded and game is unpaused')
