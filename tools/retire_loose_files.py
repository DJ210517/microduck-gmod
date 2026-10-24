"""Move only this task's loose test files aside; the installed GMA is retained."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
game=Path(r'E:\SteamLibrary\steamapps\common\GarrysMod\garrysmod').resolve()
backup=(root/'build/loose_test_backup').resolve()
owned=['lua/entities/md_microduck','lua/microduck','models/microduck','materials/microduck','materials/models/microduck']
for name in owned:
    source=(game/name).resolve()
    destination=(backup/name).resolve()
    assert source.is_relative_to(game) and source!=game
    assert destination.is_relative_to(backup) and destination!=backup
    assert not source.is_symlink()
    if source.exists():
        assert not destination.exists(),destination
        destination.parent.mkdir(parents=True,exist_ok=True)
        print('Retiring',source)
        shutil.move(str(source),str(destination))
