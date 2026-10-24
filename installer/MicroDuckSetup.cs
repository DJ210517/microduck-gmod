using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("MicroDuck Runtime Setup")]
[assembly: AssemblyVersion("0.1.0.0")]
[assembly: AssemblyDescription("Installs the matching Windows x64 MicroDuck runtime for Garry's Mod.")]

namespace MicroDuckSetup {
    sealed class Entry { public string path { get; set; } public string sha256 { get; set; } public int bytes { get; set; } }
    sealed class Manifest { public int bridge_api { get; set; } public string mujoco_version { get; set; } public Entry[] files { get; set; } }
    sealed class Payload {
        public Manifest Manifest;
        public Dictionary<string, byte[]> Files = new Dictionary<string, byte[]>();
        public static string Hash(byte[] bytes) {
            using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }
        public static Payload Read() {
            var result = new Payload();
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Runtime.zip"))
            using (var zip = new ZipArchive(stream, ZipArchiveMode.Read)) {
                foreach (var item in zip.Entries) {
                    using (var input = item.Open()) using (var memory = new MemoryStream()) {
                        input.CopyTo(memory); result.Files.Add(item.FullName, memory.ToArray());
                    }
                }
            }
            result.Manifest = new JavaScriptSerializer().Deserialize<Manifest>(Encoding.UTF8.GetString(result.Files["manifest.json"]));
            if (result.Manifest.bridge_api != 4) throw new Exception("Unsupported runtime package.");
            result.Verify(); return result;
        }
        public void Verify() {
            foreach (var entry in Manifest.files) {
                byte[] data;
                if (!Files.TryGetValue(entry.path, out data) || data.Length != entry.bytes || Hash(data) != entry.sha256)
                    throw new Exception("The embedded runtime failed verification. Download setup again.");
            }
        }
    }
    static class Installer {
        public const string Workshop = "https://steamcommunity.com/sharedfiles/filedetails/?id=3826258817";
        public const string Guide = "https://github.com/DJ210517/microduck-gmod/blob/main/INSTALL_GUIDE.md";
        public const string MicrosoftDownload = "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist";
        public static readonly string[] Names = { "gmsv_microduck_mujoco_win64.dll", "mujoco.dll" };
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr LoadLibraryEx(string path, IntPtr reserved, uint flags);
        [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr handle);
        public static string NormalizeGame(string path) {
            var root = Path.GetFullPath(path.Trim().Trim('"')).TrimEnd(Path.DirectorySeparatorChar);
            if (Path.GetFileName(root).Equals("garrysmod", StringComparison.OrdinalIgnoreCase) && File.Exists(Path.Combine(root, "gameinfo.txt"))) root = Path.GetDirectoryName(root);
            return root;
        }
        public static bool IsGame(string path) {
            try {
                var root = NormalizeGame(path);
                return File.Exists(Path.Combine(root, "garrysmod", "gameinfo.txt")) && File.Exists(Path.Combine(root, "bin", "win64", "gmod.exe"));
            } catch { return false; }
        }
        public static IEnumerable<string> Libraries(string steam) {
            var result = new List<string> { steam };
            var vdf = Path.Combine(steam, "steamapps", "libraryfolders.vdf");
            if (File.Exists(vdf)) foreach (Match m in Regex.Matches(File.ReadAllText(vdf), "\"path\"\\s*\"((?:\\\\.|[^\"\\\\])*)\""))
                result.Add(m.Groups[1].Value.Replace("\\\\", "\\"));
            return result.Distinct(StringComparer.OrdinalIgnoreCase);
        }
        public static IEnumerable<string> GamesInSteam(string steam) {
            var games = new List<string>();
            foreach (var library in Libraries(steam)) {
                var name = "GarrysMod";
                var manifest = Path.Combine(library, "steamapps", "appmanifest_4000.acf");
                if (File.Exists(manifest)) {
                    var m = Regex.Match(File.ReadAllText(manifest), "\"installdir\"\\s*\"([^\"]+)\"");
                    if (m.Success && Path.GetFileName(m.Groups[1].Value) == m.Groups[1].Value) name = m.Groups[1].Value;
                }
                var game = Path.Combine(library, "steamapps", "common", name);
                if (IsGame(game)) games.Add(NormalizeGame(game));
            }
            return games.Distinct(StringComparer.OrdinalIgnoreCase);
        }
        public static string[] Detect() {
            var roots = new List<string>();
            using (var key = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam")) {
                if (key != null && key.GetValue("SteamPath") is string) roots.Add((string)key.GetValue("SteamPath"));
            }
            foreach (var view in new[] { RegistryView.Registry32, RegistryView.Registry64 }) {
                using (var hive = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view))
                using (var key = hive.OpenSubKey(@"Software\Valve\Steam"))
                    if (key != null && key.GetValue("InstallPath") is string) roots.Add((string)key.GetValue("InstallPath"));
            }
            roots.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Steam"));
            var games = new List<string>();
            foreach (var root in roots.Distinct(StringComparer.OrdinalIgnoreCase)) {
                try { games.AddRange(GamesInSteam(root)); } catch (IOException) { } catch (UnauthorizedAccessException) { }
            }
            return games.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        }
        public static bool GameRunning() { return Process.GetProcessesByName("gmod").Length > 0; }
        public static bool MicrosoftRuntimePresent() {
            return new[] { "msvcp140.dll", "msvcp140_atomic_wait.dll", "vcruntime140.dll", "vcruntime140_1.dll" }
                .All(name => File.Exists(Path.Combine(Environment.SystemDirectory, name)));
        }
        public static void Probe(string directory) {
            foreach (var name in Names.Reverse()) {
                var handle = LoadLibraryEx(Path.Combine(directory, name), IntPtr.Zero, 0x1100);
                if (handle == IntPtr.Zero) throw new Exception("Windows could not load " + name + " (error " + Marshal.GetLastWin32Error() + "). Install Microsoft's current Visual C++ v14 x64 Redistributable, then run setup again.");
                FreeLibrary(handle);
            }
        }
        public static string Install(string path, Payload payload, Func<bool> running, Action<int> afterWrite) {
            payload.Verify();
            var game = NormalizeGame(path);
            if (!IsGame(game)) throw new Exception("Select the Garry's Mod installation folder. It must contain garrysmod/gameinfo.txt and bin/win64/gmod.exe.");
            if (running()) throw new Exception("Close Garry's Mod completely, then click Install / Repair again. Setup will not stop your game.");
            var target = Path.Combine(game, "garrysmod", "lua", "bin");
            var record = Path.Combine(game, "garrysmod", "data", "microduck_installer");
            // Reject redirected destination folders before writing the two native files.
            foreach (var relative in new[] { "garrysmod", @"garrysmod\lua", @"garrysmod\lua\bin", @"garrysmod\data", @"garrysmod\data\microduck_installer" }) {
                var folder = Path.Combine(game, relative);
                if (Directory.Exists(folder) && (File.GetAttributes(folder) & FileAttributes.ReparsePoint) != 0)
                    throw new Exception("The destination contains a redirected folder: " + folder + ". Use the manual installation guide for this layout.");
            }
            var old = new Dictionary<string, byte[]>();
            foreach (var name in Names) {
                var file = Path.Combine(target, name);
                if (File.Exists(file)) old[name] = File.ReadAllBytes(file);
            }
            string backup = null;
            var changed = Names.Where(name => !old.ContainsKey(name) || Payload.Hash(old[name]) != Payload.Hash(payload.Files["garrysmod/lua/bin/" + name])).ToArray();
            if (changed.Any(name => old.ContainsKey(name))) {
                backup = Path.Combine(record, "backups", DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ") + "-" + Guid.NewGuid().ToString("N").Substring(0, 8));
                Directory.CreateDirectory(backup);
                foreach (var name in Names.Where(old.ContainsKey)) File.WriteAllBytes(Path.Combine(backup, name), old[name]);
            }
            Directory.CreateDirectory(target);
            var written = new List<string>();
            try {
                for (var i = 0; i < changed.Length; ++i) {
                    var name = changed[i]; var destination = Path.Combine(target, name);
                    if (File.Exists(destination) && (File.GetAttributes(destination) & FileAttributes.ReparsePoint) != 0) throw new Exception("A runtime destination is a link: " + destination);
                    var temporary = destination + ".microduck-" + Guid.NewGuid().ToString("N") + ".tmp";
                    try {
                        File.WriteAllBytes(temporary, payload.Files["garrysmod/lua/bin/" + name]);
                        if (File.Exists(destination)) File.Replace(temporary, destination, null); else File.Move(temporary, destination);
                    } finally { if (File.Exists(temporary)) File.Delete(temporary); }
                    written.Add(name);
                    if (afterWrite != null) afterWrite(i);
                }
                foreach (var name in Names) if (Payload.Hash(File.ReadAllBytes(Path.Combine(target, name))) != Payload.Hash(payload.Files["garrysmod/lua/bin/" + name])) throw new Exception("Installed file verification failed: " + name);
                Probe(target);
                Directory.CreateDirectory(record);
                foreach (var name in new[] { "licenses/mujoco/LICENSE.txt", "licenses/mujoco/THIRD_PARTY.txt", "manifest.json" }) {
                    var file = Path.Combine(record, name.Replace('/', Path.DirectorySeparatorChar));
                    Directory.CreateDirectory(Path.GetDirectoryName(file)); File.WriteAllBytes(file, payload.Files[name]);
                }
                File.WriteAllText(Path.Combine(record, "install.json"), new JavaScriptSerializer().Serialize(new { installed_utc = DateTime.UtcNow.ToString("o"), game = game, bridge_api = 4, mujoco_version = payload.Manifest.mujoco_version, backup = backup, files = Names.ToDictionary(n => n, n => Payload.Hash(File.ReadAllBytes(Path.Combine(target, n)))) }));
            } catch (Exception failure) {
                var rollback = new List<string>();
                foreach (var name in written) try {
                    var file = Path.Combine(target, name);
                    if (old.ContainsKey(name)) File.WriteAllBytes(file, old[name]); else File.Delete(file);
                } catch (Exception e) { rollback.Add(name + ": " + e.Message); }
                if (rollback.Count != 0) throw new Exception(failure.Message + "\nRestoring old files also failed. Backup: " + backup + "\n" + String.Join("\n", rollback));
                throw new Exception(failure.Message + "\nThe previous runtime files were restored.", failure);
            }
            return backup;
        }
    }
    sealed class SetupForm : Form {
        ComboBox folder; Label status; Button install; Payload payload;
        public SetupForm(Payload data) {
            payload = data; Text = "MicroDuck Runtime Setup"; ClientSize = new Size(640, 410);
            Font = new Font("Segoe UI", 10); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen; BackColor = Color.FromArgb(246, 248, 250);
            var title = new Label { Text = "MicroDuck, ready to waddle.", Font = new Font("Segoe UI", 20, FontStyle.Bold), Location = new Point(24, 20), AutoSize = true }; Controls.Add(title);
            Controls.Add(new Label { Text = "Subscribe on Workshop. Close GMod. Install the runtime once.", Location = new Point(26, 66), AutoSize = true });
            Controls.Add(new Label { Text = "Garry's Mod installation", Location = new Point(26, 110), AutoSize = true });
            folder = new ComboBox { Location = new Point(26, 137), Size = new Size(477, 28), DropDownStyle = ComboBoxStyle.DropDown };
            Controls.Add(folder);
            var browse = new Button { Text = "Browse...", Location = new Point(513, 135), Size = new Size(100, 30) };
            browse.Click += delegate { using (var dialog = new FolderBrowserDialog { Description = "Choose the Garry's Mod installation folder", ShowNewFolderButton = false }) if (dialog.ShowDialog(this) == DialogResult.OK) { folder.Text = dialog.SelectedPath; RefreshStatus(); } }; Controls.Add(browse);
            status = new Label { Location = new Point(26, 182), Size = new Size(587, 94) }; Controls.Add(status);
            install = new Button { Text = "Install / Repair Runtime", Location = new Point(26, 286), Size = new Size(266, 43), BackColor = Color.FromArgb(255, 201, 63), FlatStyle = FlatStyle.Flat };
            install.Click += delegate { DoInstall(); }; Controls.Add(install);
            var workshop = new Button { Text = "Open Workshop", Location = new Point(310, 286), Size = new Size(145, 43) }; workshop.Click += delegate { Open(Installer.Workshop); }; Controls.Add(workshop);
            var guide = new Button { Text = "Install Guide", Location = new Point(468, 286), Size = new Size(145, 43) }; guide.Click += delegate { Open(Installer.Guide); }; Controls.Add(guide);
            var ms = new LinkLabel { Text = "Microsoft Visual C++ x64 download", Location = new Point(26, 346), AutoSize = true }; ms.LinkClicked += delegate { Open(Installer.MicrosoftDownload); }; Controls.Add(ms);
            var licenses = new LinkLabel { Text = "License notices", Location = new Point(480, 346), AutoSize = true }; licenses.LinkClicked += delegate { ShowLicenses(); }; Controls.Add(licenses);
            folder.TextChanged += delegate { RefreshStatus(); };
            Shown += delegate {
                try { foreach (var path in Installer.Detect()) folder.Items.Add(path); if (folder.Items.Count > 0) folder.SelectedIndex = 0; RefreshStatus(); }
                catch (Exception e) { status.Text = "Auto-detection failed. Browse to your GMod folder.\n" + e.Message; }
            };
        }
        static void Open(string url) { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); }
        void RefreshStatus() {
            if (!Installer.IsGame(folder.Text)) { status.Text = "Choose your GMod folder, or use Browse. Setup finds Steam libraries automatically."; return; }
            var messages = new List<string>();
            messages.Add(Installer.GameRunning() ? "Close Garry's Mod completely before installing." : "GMod found. Ready to install the matching runtime.");
            messages.Add(Installer.MicrosoftRuntimePresent() ? "Microsoft Visual C++ x64 runtime detected." : "Microsoft Visual C++ x64 runtime may need updating. Use the download link below.");
            var game = Installer.NormalizeGame(folder.Text);
            if (Directory.Exists(Path.Combine(game, "garrysmod", "addons", "microduck_real_ai"))) messages.Add("Old loose addon found: use that copy OR Workshop. See the guide before subscribing.");
            status.Text = String.Join("\n", messages);
        }
        void DoInstall() {
            install.Enabled = false; UseWaitCursor = true;
            try {
                var backup = Installer.Install(folder.Text, payload, Installer.GameRunning, null);
                status.Text = "Installed and verified! Start 64-bit GMod, then spawn your duck.\nThe same setup program repairs or updates these two runtime files." + (backup == null ? "" : "\nPrevious files backed up under garrysmod/data/microduck_installer.");
                MessageBox.Show(this, "Runtime installed and verified.\n\nMake sure the Workshop addon is subscribed, then start 64-bit GMod.\nEntities > MicroDuck\nWeapons > MicroDuck > MicroDuck Remote", "MicroDuck is ready", MessageBoxButtons.OK, MessageBoxIcon.Information);
            } catch (UnauthorizedAccessException) { MessageBox.Show(this, "Windows denied access to this game folder. Choose an installation you can write to, or use the manual guide. No security settings were changed.", "Could not install", MessageBoxButtons.OK, MessageBoxIcon.Warning); RefreshStatus(); }
            catch (Exception e) { MessageBox.Show(this, e.Message, "Could not install", MessageBoxButtons.OK, MessageBoxIcon.Warning); RefreshStatus(); }
            finally { install.Enabled = true; UseWaitCursor = false; }
        }
        void ShowLicenses() {
            using (var window = new Form { Text = "MicroDuck runtime license notices", Size = new Size(760, 600), StartPosition = FormStartPosition.CenterParent }) {
                window.Controls.Add(new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false, Dock = DockStyle.Fill, Text = String.Join("\r\n\r\n", new[] { "licenses/mujoco/LICENSE.txt", "licenses/mujoco/THIRD_PARTY.txt" }.Select(n => n + "\r\n" + Encoding.UTF8.GetString(payload.Files[n]))) }); window.ShowDialog(this);
            }
        }
    }
    static class Program {
        [STAThread] static int Main(string[] args) {
            try {
                var payload = Payload.Read();
                if (args.Length == 2 && args[0] == "--self-test") return Tests.Run(payload, args[1]);
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new SetupForm(payload)); return 0;
            } catch (Exception e) {
                if (args.Length > 0) { File.WriteAllText(args[args.Length - 1] + ".error.txt", e.ToString()); return 1; }
                MessageBox.Show(e.Message, "MicroDuck setup", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1;
            }
        }
    }
}
