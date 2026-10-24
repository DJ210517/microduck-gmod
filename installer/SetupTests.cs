using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;

namespace MicroDuckSetup {
    static class Tests {
        static void Assert(bool value, string name) { if (!value) throw new Exception("Failed: " + name); }
        static void Reject(Action action, string name) {
            bool rejected = false; try { action(); } catch { rejected = true; } Assert(rejected, name);
        }
        static void MakeGame(string root) {
            Directory.CreateDirectory(Path.Combine(root, "garrysmod"));
            File.WriteAllText(Path.Combine(root, "garrysmod", "gameinfo.txt"), "test fixture");
            Directory.CreateDirectory(Path.Combine(root, "bin", "win64"));
            File.WriteAllBytes(Path.Combine(root, "bin", "win64", "gmod.exe"), new byte[0]);
        }
        public static int Run(Payload payload, string directory) {
            directory = Path.GetFullPath(directory);
            Assert(Path.GetFileName(directory) == "installer_fixture", "dedicated fixture directory required");
            Directory.CreateDirectory(directory);
            var checks = new List<string>();
            var game = Path.Combine(directory, "fixture-game"); MakeGame(game);
            var target = Path.Combine(game, "garrysmod", "lua", "bin");
            Assert(Installer.IsGame(game) && Installer.NormalizeGame(Path.Combine(game, "garrysmod")) == game, "root and nested folder detection"); checks.Add("root and nested folder detection");
            Reject(() => Installer.Install(directory, payload, () => false, null), "wrong game rejected"); checks.Add("wrong game rejected");
            Reject(() => Installer.Install(game, payload, () => true, null), "running game rejected");
            Assert(!Directory.Exists(target), "running game wrote nothing"); checks.Add("running game blocked before writes");
            var key = "garrysmod/lua/bin/mujoco.dll"; var original = payload.Files[key];
            payload.Files[key] = new byte[] { 1, 2 };
            Reject(() => Installer.Install(game, payload, () => false, null), "damaged embedded payload rejected");
            payload.Files[key] = original; checks.Add("embedded checksum damage rejected");
            var backup = Installer.Install(game, payload, () => false, null);
            Assert(backup == null && Installer.Names.All(n => File.Exists(Path.Combine(target, n))), "fresh install"); checks.Add("fresh install and actual Windows DLL loading");
            Assert(Installer.Install(game, payload, () => false, null) == null, "idempotent repair"); checks.Add("already matching install verified without backup");
            var old = new byte[] { 10, 20, 30 };
            foreach (var name in Installer.Names) File.WriteAllBytes(Path.Combine(target, name), old);
            Reject(() => Installer.Install(game, payload, () => false, i => { throw new Exception("injected write failure"); }), "injected failure");
            Assert(Installer.Names.All(n => File.ReadAllBytes(Path.Combine(target, n)).SequenceEqual(old)), "rollback preserves both previous files"); checks.Add("partial update failure restored both previous files");
            backup = Installer.Install(game, payload, () => false, null);
            Assert(backup != null && Installer.Names.All(n => File.ReadAllBytes(Path.Combine(backup, n)).SequenceEqual(old)), "upgrade backups"); checks.Add("upgrade preserved previous DLL bytes in backup");
            File.WriteAllText(Path.Combine(target, "unrelated.txt"), "keep me");
            Installer.Install(game, payload, () => false, null);
            Assert(File.ReadAllText(Path.Combine(target, "unrelated.txt")) == "keep me", "unrelated file preserved"); checks.Add("unrelated game files preserved");
            var steam = Path.Combine(directory, "Steam fixture"); var library = Path.Combine(directory, "Library with spaces");
            Directory.CreateDirectory(Path.Combine(steam, "steamapps")); Directory.CreateDirectory(Path.Combine(library, "steamapps"));
            File.WriteAllText(Path.Combine(steam, "steamapps", "libraryfolders.vdf"), "\"libraryfolders\" { \"0\" { \"path\" \"" + steam.Replace("\\", "\\\\") + "\" } \"1\" { \"path\" \"" + library.Replace("\\", "\\\\") + "\" } }");
            File.WriteAllText(Path.Combine(library, "steamapps", "appmanifest_4000.acf"), "\"AppState\" { \"appid\" \"4000\" \"installdir\" \"GarrysMod Custom\" }");
            var custom = Path.Combine(library, "steamapps", "common", "GarrysMod Custom"); MakeGame(custom);
            Assert(Installer.GamesInSteam(steam).SequenceEqual(new[] { custom }), "multi library custom folder detection"); checks.Add("Steam VDF multi-library discovery with spaces and custom install directory");
            var detected = Installer.Detect();
            var report = new { passed = true, checks = checks, actual_games_detected_read_only = detected, microsoft_runtime_present = Installer.MicrosoftRuntimePresent(), actual_gmod_running = Installer.GameRunning(), production_game_modified = false };
            File.WriteAllText(Path.Combine(directory, "results.json"), new JavaScriptSerializer().Serialize(report), Encoding.UTF8);
            return 0;
        }
    }
}
