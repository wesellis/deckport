import { useState, useEffect, useRef } from "react";
import {
  Image as ImageIcon, FolderTree, UploadCloud, HardDriveDownload,
  FileCog, KeyRound, LayoutGrid, Gamepad2, Play, RotateCcw,
  Check, Wifi, Cpu,
} from "lucide-react";

// ── palette (inline styles; Tailwind handles layout only) ──────────────
const C = {
  ink: "#0c1016", panel: "#141b24", panel2: "#1b2530", line: "#2a3644",
  text: "#e7eef6", sub: "#8595a8", amber: "#ffb454", amberDim: "#7a5a2a",
  cyan: "#46c8f0", green: "#5fd882", mag: "#cf7fe0",
};

const STEPS = [
  { id: "art",      zone: "pc",     node: "Fetch",     title: "Fetch artwork",
    detail: "VAPOR searches SteamGridDB by game name and pulls cover, hero, logo, icon.",
    Icon: ImageIcon, color: C.mag },
  { id: "stage",    zone: "pc",     node: "Bundle",    title: "Bundle into the folder",
    detail: "Art lands in .deckport-art/ inside the game folder — generic names, no IDs yet.",
    Icon: FolderTree, color: C.mag },
  { id: "push",     zone: "bridge", node: "Push",      title: "Push over SSH",
    detail: "One rsync / SFTP transfer carries the game and its art to ~/Games on the Deck.",
    Icon: UploadCloud, color: C.cyan },
  { id: "land",     zone: "deck",   node: "Land",      title: "Land in ~/Games",
    detail: "The whole folder arrives intact — binary, .pck / .nes data, and art together.",
    Icon: HardDriveDownload, color: C.amber },
  { id: "detect",   zone: "deck",   node: "Unlock",    title: "Detect & unlock",
    detail: "Finds the real Linux binary and sets the execute bit that FTP strips away.",
    Icon: FileCog, color: C.amber },
  { id: "register", zone: "deck",   node: "Register",  title: "Generate ID & register",
    detail: "Computes the shortcut ID, writes the entry into shortcuts.vdf.",
    Icon: KeyRound, color: C.amber },
  { id: "install",  zone: "deck",   node: "Dress",     title: "Install artwork",
    detail: "Renames bundled art to grid/{id}p.jpg, _hero, _logo — keyed to that same ID.",
    Icon: LayoutGrid, color: C.amber },
  { id: "play",     zone: "deck",   node: "Game Mode", title: "Appears in Game Mode",
    detail: "Restart Steam, drop into Game Mode — controller-ready and fully dressed.",
    Icon: Gamepad2, color: C.green },
];
const LAST = STEPS.length - 1;
const APPID = "3580912219";

export default function DeckportPipeline() {
  const [phase, setPhase] = useState(-1);   // -1 idle, 0..LAST active, LAST=done
  const [running, setRunning] = useState(false);
  const timer = useRef(null);
  const reduce = useRef(false);

  useEffect(() => {
    reduce.current = typeof window !== "undefined" &&
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    if (!running) return;
    if (phase >= LAST) { setRunning(false); return; }
    timer.current = setTimeout(() => setPhase((p) => p + 1), reduce.current ? 1400 : 950);
    return () => clearTimeout(timer.current);
  }, [running, phase]);

  const run = () => { if (phase >= LAST || phase < 0) setPhase(0); setRunning(true); };
  const reset = () => { setRunning(false); setPhase(-1); clearTimeout(timer.current); };
  const next = () => { setRunning(false); setPhase((p) => Math.min(LAST, p + 1)); };

  const active = phase >= 0 ? STEPS[phase] : null;
  const done = (i) => phase > i || phase === LAST;
  const zoneLit = (z) => active && active.zone === z;
  const reached = (id) => {
    const i = STEPS.findIndex((s) => s.id === id);
    return phase >= i;
  };

  return (
    <div className="w-full min-h-full p-4 sm:p-6 font-sans"
         style={{ background: C.ink, color: C.text }}>
      <div className="mx-auto" style={{ maxWidth: 1080 }}>

        {/* header */}
        <div className="flex flex-wrap items-end justify-between gap-4 mb-1">
          <div>
            <div className="flex items-center gap-2">
              <Cpu size={18} style={{ color: C.amber }} />
              <span className="font-mono text-lg tracking-widest" style={{ color: C.amber }}>
                deckport
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded"
                    style={{ background: C.panel2, color: C.sub, border: `1px solid ${C.line}` }}>
                pipeline
              </span>
            </div>
            <p className="mt-2 text-sm sm:text-base" style={{ color: C.sub }}>
              Drop a game on your PC — it lands on your Deck, fully dressed, in Game&nbsp;Mode.
            </p>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <button onClick={run}
              className="flex items-center gap-1.5 px-3 py-2 rounded-md transition-colors"
              style={{ background: running ? C.panel2 : C.amber, color: running ? C.sub : C.ink,
                       border: `1px solid ${running ? C.line : C.amber}` }}>
              <Play size={14} /> {phase >= LAST ? "Replay" : running ? "Running" : "Run"}
            </button>
            <button onClick={next} disabled={phase >= LAST}
              className="px-3 py-2 rounded-md transition-colors"
              style={{ background: C.panel, color: phase >= LAST ? C.amberDim : C.text,
                       border: `1px solid ${C.line}` }}>
              Step
            </button>
            <button onClick={reset}
              className="flex items-center gap-1.5 px-3 py-2 rounded-md"
              style={{ background: C.panel, color: C.sub, border: `1px solid ${C.line}` }}>
              <RotateCcw size={14} /> Reset
            </button>
          </div>
        </div>

        {/* progress rail */}
        <div className="flex items-center gap-1 my-5">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-1" style={{ flex: 1 }}>
              <div className="flex flex-col items-center" style={{ width: 0, flex: 1 }}>
                <div className="flex items-center justify-center rounded-full transition-all"
                     style={{
                       width: 30, height: 30,
                       background: done(i) ? s.color : phase === i ? C.panel2 : C.panel,
                       border: `2px solid ${phase === i ? s.color : done(i) ? s.color : C.line}`,
                       boxShadow: phase === i ? `0 0 14px ${s.color}` : "none",
                       color: done(i) ? C.ink : phase === i ? s.color : C.sub,
                     }}>
                  {done(i) ? <Check size={15} /> : <s.Icon size={15} />}
                </div>
                <span className="hidden sm:block font-mono mt-1.5 text-center"
                      style={{ fontSize: 9.5, color: phase === i ? s.color : C.sub }}>
                  {s.node}
                </span>
              </div>
              {i < LAST && (
                <div className="rounded-full transition-all" style={{
                  height: 2, flex: 1.2,
                  background: phase > i ? STEPS[i + 1].color : C.line,
                }} />
              )}
            </div>
          ))}
        </div>

        {/* zones */}
        <div className="grid gap-3" style={{ gridTemplateColumns: "1fr" }}>
          <div className="grid gap-3" style={{ gridTemplateColumns: "minmax(0,1fr)" }}>
            <div className="grid gap-3 sm:grid-cols-12">

              {/* PC zone */}
              <Zone className="sm:col-span-4" label="YOUR PC" lit={zoneLit("pc")}
                    accent={C.mag} sub="artwork + transfer source">
                <Card lit={reached("art")} accent={C.mag} Icon={ImageIcon}
                      title="VAPOR → SteamGridDB"
                      body="Search by name, pull cover · hero · logo · icon." />
                <Wire on={reached("stage")} accent={C.mag} />
                <Card lit={reached("stage")} accent={C.mag} Icon={FolderTree}
                      title=".deckport-art/"
                      mono={["cover.jpg", "hero.jpg", "logo.png", "icon.png"]} />
              </Zone>

              {/* bridge */}
              <div className="sm:col-span-4 flex flex-col items-center justify-center py-2">
                <div className="w-full rounded-xl p-4 text-center transition-all"
                     style={{ background: C.panel,
                              border: `1px solid ${zoneLit("bridge") ? C.cyan : C.line}`,
                              boxShadow: zoneLit("bridge") ? `0 0 22px ${C.cyan}33` : "none" }}>
                  <Wifi size={18} style={{ color: C.cyan }} className="mx-auto" />
                  <div className="font-mono text-xs mt-2" style={{ color: C.cyan }}>FTP over SSH</div>
                  <div className="text-xs mt-1" style={{ color: C.sub }}>one transfer, game + art</div>

                  {/* travelling cartridge */}
                  <div className="relative mt-4 mx-auto rounded-full"
                       style={{ height: 4, background: C.line, maxWidth: 200 }}>
                    <div className="absolute rounded-full transition-all"
                         style={{ height: 4, left: 0,
                                  width: reached("land") ? "100%" : reached("push") ? "55%" : "0%",
                                  background: C.cyan, transitionDuration: "800ms" }} />
                    <div className="absolute rounded-sm transition-all"
                         style={{ top: -7, width: 18, height: 18,
                                  transform: "translateX(-50%)",
                                  left: reached("land") ? "100%" : reached("push") ? "55%" : "0%",
                                  background: zoneLit("bridge") || reached("land") ? C.cyan : C.panel2,
                                  border: `2px solid ${C.cyan}`,
                                  boxShadow: zoneLit("bridge") ? `0 0 12px ${C.cyan}` : "none",
                                  transitionDuration: "800ms", opacity: phase >= 2 ? 1 : 0.3 }} />
                  </div>
                  <div className="font-mono mt-2" style={{ fontSize: 10, color: C.sub }}>
                    deck@steamdeck:~/Games
                  </div>
                </div>
              </div>

              {/* Deck zone */}
              <Zone className="sm:col-span-4" label="STEAM DECK" lit={zoneLit("deck")}
                    accent={C.amber} sub="deckport.py — stdlib only">
                {STEPS.filter((s) => s.zone === "deck" && s.id !== "play").map((s) => (
                  <DeckStep key={s.id} on={reached(s.id)} active={active && active.id === s.id}
                            accent={s.color} Icon={s.Icon} title={s.title} />
                ))}
                {/* game-mode tile */}
                <div className="mt-1 rounded-lg p-3 transition-all"
                     style={{ background: C.panel2,
                              border: `1px solid ${reached("play") ? C.green : C.line}`,
                              boxShadow: active && active.id === "play" ? `0 0 20px ${C.green}55` : "none" }}>
                  <div className="flex items-center gap-2 mb-2">
                    <Gamepad2 size={14} style={{ color: reached("play") ? C.green : C.sub }} />
                    <span className="font-mono text-xs"
                          style={{ color: reached("play") ? C.green : C.sub }}>Game Mode</span>
                  </div>
                  <Tile dressed={reached("install")} />
                </div>
              </Zone>

            </div>
          </div>
        </div>

        {/* status line */}
        <div className="mt-4 rounded-lg px-4 py-3 font-mono text-xs sm:text-sm flex items-start gap-3"
             style={{ background: C.panel, border: `1px solid ${C.line}` }}>
          <span style={{ color: active ? active.color : C.sub }}>
            {phase < 0 ? "›" : phase >= LAST ? "✓" : "▸"}
          </span>
          <span style={{ color: C.text }}>
            {phase < 0
              ? "Press Run to watch a game travel from your PC to the Deck."
              : active
              ? <><b style={{ color: active.color }}>{active.title}.</b>{" "}
                  <span style={{ color: C.sub }}>{active.detail}</span></>
              : ""}
          </span>
        </div>

        {/* appid linchpin */}
        <div className="mt-3 rounded-xl p-4"
             style={{ background: C.panel,
                      border: `1px solid ${reached("install") ? C.amber : C.line}`,
                      transition: "border-color .4s" }}>
          <div className="flex items-center gap-2 mb-3">
            <KeyRound size={15} style={{ color: C.amber }} />
            <span className="font-mono text-xs tracking-wide" style={{ color: C.amber }}>
              the linchpin — one ID names both
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-12 items-center">
            <Chip className="sm:col-span-4" lit={reached("register")} accent={C.amber}
                  top="shortcuts.vdf" mid={`appid → ${APPID}`} bot="the launcher entry" />
            <div className="sm:col-span-4 flex flex-col items-center justify-center">
              <div className="font-mono text-center" style={{ fontSize: 11, color: C.sub }}>
                crc32(exe + name)
              </div>
              <div className="w-full my-2 rounded-full" style={{
                height: 3, background: reached("install")
                  ? `linear-gradient(90deg, ${C.amber}, ${C.green})` : C.line,
                transition: "background .5s",
              }} />
              <div className="font-mono text-center" style={{ fontSize: 11, color: C.sub }}>
                computed once, on the Deck
              </div>
            </div>
            <Chip className="sm:col-span-4" lit={reached("install")} accent={C.green}
                  top="config/grid/" mid={`${APPID}p.jpg`} bot="the box art Steam shows" />
          </div>
        </div>

        <p className="mt-4 text-center text-xs" style={{ color: C.sub }}>
          PC half carries the dependencies (requests · Pillow). Deck half stays pure stdlib.
        </p>
      </div>
    </div>
  );
}

// ── small components ───────────────────────────────────────────────────
function Zone({ label, sub, lit, accent, children, className = "" }) {
  return (
    <div className={`rounded-xl p-3 transition-all ${className}`}
         style={{ background: C.panel, border: `1px solid ${lit ? accent : C.line}`,
                  boxShadow: lit ? `0 0 22px ${accent}22` : "none" }}>
      <div className="flex items-baseline justify-between mb-2">
        <span className="font-mono text-xs tracking-widest"
              style={{ color: lit ? accent : C.sub }}>{label}</span>
      </div>
      <div className="text-xs mb-3" style={{ color: C.sub }}>{sub}</div>
      <div className="flex flex-col gap-0">{children}</div>
    </div>
  );
}

function Card({ lit, accent, Icon, title, body, mono }) {
  return (
    <div className="rounded-lg p-3 transition-all"
         style={{ background: lit ? C.panel2 : C.panel,
                  border: `1px solid ${lit ? accent : C.line}`,
                  opacity: lit ? 1 : 0.6 }}>
      <div className="flex items-center gap-2">
        <Icon size={15} style={{ color: lit ? accent : C.sub }} />
        <span className="font-mono text-xs" style={{ color: lit ? C.text : C.sub }}>{title}</span>
      </div>
      {body && <div className="text-xs mt-1.5" style={{ color: C.sub }}>{body}</div>}
      {mono && (
        <div className="flex flex-wrap gap-1 mt-2">
          {mono.map((m) => (
            <span key={m} className="font-mono rounded px-1.5 py-0.5"
                  style={{ fontSize: 10, background: C.ink, color: lit ? accent : C.sub,
                           border: `1px solid ${C.line}` }}>{m}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function Wire({ on, accent }) {
  return (
    <div className="flex justify-center" style={{ height: 14 }}>
      <div className="rounded-full transition-all"
           style={{ width: 2, background: on ? accent : C.line }} />
    </div>
  );
}

function DeckStep({ on, active, accent, Icon, title }) {
  return (
    <div className="flex items-center gap-2 rounded-lg px-3 py-2 mb-1.5 transition-all"
         style={{ background: active ? C.panel2 : C.panel,
                  border: `1px solid ${active ? accent : on ? C.amberDim : C.line}`,
                  boxShadow: active ? `0 0 14px ${accent}44` : "none",
                  opacity: on ? 1 : 0.55 }}>
      <div className="flex items-center justify-center rounded-md"
           style={{ width: 24, height: 24, background: on ? accent : C.line,
                    color: on ? C.ink : C.sub, flexShrink: 0 }}>
        {on && !active ? <Check size={13} /> : <Icon size={13} />}
      </div>
      <span className="font-mono text-xs" style={{ color: on ? C.text : C.sub }}>{title}</span>
    </div>
  );
}

function Tile({ dressed }) {
  return (
    <div className="flex items-center gap-3">
      <div className="rounded-md overflow-hidden flex items-center justify-center transition-all"
           style={{ width: 56, height: 84, flexShrink: 0,
                    background: dressed
                      ? "linear-gradient(150deg, #2a4d8f 0%, #c0392b 60%, #e67e22 100%)"
                      : C.ink,
                    border: `1px solid ${dressed ? "transparent" : C.line}` }}>
        {dressed
          ? <span className="font-mono text-center px-1"
                  style={{ fontSize: 8, lineHeight: 1.1, color: "#fff", fontWeight: 700 }}>
              SMB<br />REMASTERED
            </span>
          : <ImageIcon size={18} style={{ color: C.sub }} />}
      </div>
      <div>
        <div className="font-mono text-xs" style={{ color: dressed ? C.text : C.sub }}>
          Super Mario Bros. Remastered
        </div>
        <div className="text-xs mt-0.5" style={{ color: dressed ? C.green : C.sub }}>
          {dressed ? "artwork applied" : "placeholder capsule"}
        </div>
      </div>
    </div>
  );
}

function Chip({ lit, accent, top, mid, bot, className = "" }) {
  return (
    <div className={`rounded-lg p-3 transition-all ${className}`}
         style={{ background: lit ? C.panel2 : C.panel,
                  border: `1px solid ${lit ? accent : C.line}`,
                  boxShadow: lit ? `0 0 16px ${accent}33` : "none" }}>
      <div className="font-mono" style={{ fontSize: 10, color: C.sub }}>{top}</div>
      <div className="font-mono text-sm my-1" style={{ color: lit ? accent : C.sub }}>{mid}</div>
      <div className="text-xs" style={{ color: C.sub }}>{bot}</div>
    </div>
  );
}
