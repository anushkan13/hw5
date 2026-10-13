/**
 * An original bulldog character, drawn from scratch as SVG.
 *
 * Not based on any real mascot or logo. The proportions are my own and are
 * chosen to read as "bulldog" at small sizes: a low wide skull, rose ears
 * folded back, three brow wrinkles, a broad flat muzzle set low, a modest
 * underbite with two visible bottom teeth, and heavy jowls that hang past the
 * jawline. Every agent is the same dog in a different coloured apron, so the
 * team reads as one crew rather than five unrelated drawings.
 *
 * The whole scene — stool, dog, paws on the desk, desk, supplies, name tag —
 * lives in one viewBox so it scales as a unit. The viewBox starts above y=0
 * to leave headroom for the Boss's crown.
 */

interface Props {
  apron: string;
  apronDark: string;
  name: string;
  crown?: boolean;
  /** The dog looks toward whichever agent it is talking to. */
  gaze?: "left" | "right" | "center";
  speaking?: boolean;
}

const FUR = "#EFE9DE";
const FUR_SHADE = "#D8CEBE";
const FUR_LINE = "#BFB2A0";
const MUZZLE = "#FCFAF5";
const DARK = "#2A2724";
const DESK_TOP = "#5E4535";
const DESK_FACE = "#3E2C21";
const DESK_EDGE = "#2B1E17";
const STOOL = "#6B5140";

export default function Bulldog({
  apron,
  apronDark,
  name,
  crown = false,
  gaze = "center",
  speaking = false,
}: Props) {
  const look = gaze === "left" ? -4 : gaze === "right" ? 4 : 0;

  // Long names need a wider plate and smaller lettering to stay inside it.
  const tagW = Math.max(108, Math.min(176, name.length * 9 + 34));
  const tagX = 120 - tagW / 2;
  const tagFont = name.length > 13 ? 10.5 : name.length > 9 ? 11.5 : 13;

  return (
    <svg
      viewBox="0 -18 240 266"
      className={`bulldog ${speaking ? "is-speaking" : ""}`}
      role="img"
      aria-label={`${name} bulldog at a desk`}
    >
      {/* ---------------------------- stool ---------------------------- */}
      <g className="stool">
        <rect x="103" y="168" width="10" height="56" rx="5" fill={STOOL} />
        <rect x="127" y="168" width="10" height="56" rx="5" fill={STOOL} />
        <rect x="98" y="214" width="44" height="7" rx="3.5" fill="#56402F" />
      </g>

      {/* --------------------------- body ------------------------------ */}
      <g className="body">
        <path d="M70 186 C70 136 94 114 120 114 C146 114 170 136 170 186 Z" fill={FUR} />
        <path d="M70 186 C70 156 82 134 98 122 L96 186 Z" fill={FUR_SHADE} opacity=".5" />

        {/* apron: bib, then skirt, sized so plenty shows above the desk */}
        <path d="M98 120 C98 113 142 113 142 120 L142 144 C142 152 98 152 98 144 Z" fill={apron} />
        <path d="M88 144 L152 144 L164 186 L76 186 Z" fill={apron} />
        <path d="M88 144 L103 144 L95 186 L76 186 Z" fill={apronDark} opacity=".45" />
        {/* straps */}
        <path d="M102 120 L94 110" stroke={apronDark} strokeWidth="5.5" strokeLinecap="round" />
        <path d="M138 120 L146 110" stroke={apronDark} strokeWidth="5.5" strokeLinecap="round" />
        {/* chest pocket */}
        <rect x="106" y="154" width="28" height="18" rx="3" fill={apronDark} opacity=".5" />
        <path d="M114 154 V172 M126 154 V172" stroke={apron} strokeWidth="1.6" opacity=".55" />

        {/* collar + tag */}
        <path d="M94 112 C107 121 133 121 146 112" stroke={apronDark} strokeWidth="9" fill="none" strokeLinecap="round" />
        <circle cx="120" cy="122" r="5.5" fill="#D9B35C" stroke="#A8853A" strokeWidth="1.6" />
      </g>

      {/* ---------------------------- head ----------------------------- */}
      <g className="head">
        {/* rose ears, folded back and set low on a wide skull */}
        <path d="M74 44 C58 34 44 44 48 60 C52 76 70 80 80 70 Z" fill={FUR_SHADE} stroke={FUR_LINE} strokeWidth="1.5" />
        <path d="M166 44 C182 34 196 44 192 60 C188 76 170 80 160 70 Z" fill={FUR_SHADE} stroke={FUR_LINE} strokeWidth="1.5" />
        <path d="M68 50 C58 48 52 54 54 62" stroke={FUR_LINE} strokeWidth="2.2" fill="none" strokeLinecap="round" />
        <path d="M172 50 C182 48 188 54 186 62" stroke={FUR_LINE} strokeWidth="2.2" fill="none" strokeLinecap="round" />

        {/* skull: wide and low */}
        <path
          d="M120 18 C160 18 180 40 180 72 C180 106 154 122 120 122 C86 122 60 106 60 72 C60 40 80 18 120 18 Z"
          fill={FUR}
        />
        <path d="M60 72 C60 46 74 26 98 20 C76 36 68 54 68 74 C68 98 84 112 104 118 C78 115 60 98 60 72 Z" fill={FUR_SHADE} opacity=".55" />

        {/* three brow wrinkles — the bulldog tell */}
        <path d="M94 38 C108 31 132 31 146 38" stroke={FUR_LINE} strokeWidth="3.4" fill="none" strokeLinecap="round" />
        <path d="M88 48 C105 39 135 39 152 48" stroke={FUR_LINE} strokeWidth="3.4" fill="none" strokeLinecap="round" />
        <path d="M92 58 C106 51 134 51 148 58" stroke={FUR_LINE} strokeWidth="2.8" fill="none" strokeLinecap="round" opacity=".75" />

        {/* eyes, set wide */}
        <ellipse cx="97" cy="71" rx="10.5" ry="11.5" fill="#FFF" />
        <ellipse cx="143" cy="71" rx="10.5" ry="11.5" fill="#FFF" />
        <circle cx={97 + look} cy="72" r="5.8" fill={DARK} />
        <circle cx={143 + look} cy="72" r="5.8" fill={DARK} />
        <circle cx={99 + look} cy="69" r="2" fill="#FFF" />
        <circle cx={145 + look} cy="69" r="2" fill="#FFF" />
        <path d="M86 61 C92 56 104 56 110 61" stroke={DARK} strokeWidth="3.2" fill="none" strokeLinecap="round" opacity=".8" />
        <path d="M130 61 C136 56 148 56 154 61" stroke={DARK} strokeWidth="3.2" fill="none" strokeLinecap="round" opacity=".8" />

        {/* jowls hanging past the jaw */}
        <path d="M74 92 C72 112 86 126 104 126 C92 118 86 106 86 94 Z" fill={FUR_SHADE} opacity=".8" />
        <path d="M166 92 C168 112 154 126 136 126 C148 118 154 106 154 94 Z" fill={FUR_SHADE} opacity=".8" />

        {/* broad muzzle set low */}
        <path
          d="M120 80 C150 80 164 92 164 105 C164 120 144 128 120 128 C96 128 76 120 76 105 C76 92 90 80 120 80 Z"
          fill={MUZZLE}
        />
        <path d="M80 106 C80 120 100 127 120 127 C110 120 105 112 105 100 Z" fill="#F0E9DC" opacity=".65" />

        {/* nose: big, flat, slightly upturned */}
        <path d="M106 86 C106 80 134 80 134 86 L131 97 C128 101 112 101 109 97 Z" fill={DARK} />
        <ellipse cx="113" cy="88" rx="2.4" ry="3.2" fill="#55504B" />
        <ellipse cx="127" cy="88" rx="2.4" ry="3.2" fill="#55504B" />
        <path d="M120 84 L120 97" stroke="#15130F" strokeWidth="1.6" opacity=".55" />

        {/* mouth + underbite */}
        <path d="M120 100 L120 107" stroke={DARK} strokeWidth="2.8" strokeLinecap="round" />
        <path d="M120 107 C111 116 99 114 94 106" stroke={DARK} strokeWidth="2.8" fill="none" strokeLinecap="round" />
        <path d="M120 107 C129 116 141 114 146 106" stroke={DARK} strokeWidth="2.8" fill="none" strokeLinecap="round" />
        <rect x="109" y="105" width="7" height="8.5" rx="2.2" fill="#FFF" stroke="#CFC8BA" strokeWidth=".9" />
        <rect x="124" y="105" width="7" height="8.5" rx="2.2" fill="#FFF" stroke="#CFC8BA" strokeWidth=".9" />
      </g>

      {/* --------------------------- crown ----------------------------- */}
      {crown && (
        <g className="crown">
          <path
            d="M82 20 L90 -10 L105 8 L120 -16 L135 8 L150 -10 L158 20 Z"
            fill="#E8C268"
            stroke="#A8853A"
            strokeWidth="2.6"
            strokeLinejoin="round"
          />
          <rect x="82" y="17" width="76" height="11" rx="5" fill="#D4A94F" stroke="#A8853A" strokeWidth="2.2" />
          <circle cx="120" cy="-2" r="4" fill="#8FB8E8" stroke="#A8853A" strokeWidth="1.4" />
          <circle cx="93" cy="4" r="2.8" fill="#C98A8A" stroke="#A8853A" strokeWidth="1.1" />
          <circle cx="147" cy="4" r="2.8" fill="#C98A8A" stroke="#A8853A" strokeWidth="1.1" />
          <circle cx="120" cy="22.5" r="2.6" fill="#8FB8E8" />
        </g>
      )}

      {/* --------------- paws resting on the desk top ------------------ */}
      <g className="paws">
        <ellipse cx="78" cy="176" rx="15" ry="10" fill={FUR} stroke={FUR_LINE} strokeWidth="1.4" />
        <path d="M70 174 h16 M74 170 v10" stroke={FUR_LINE} strokeWidth="1.3" opacity=".8" />
        <ellipse cx="162" cy="176" rx="15" ry="10" fill={FUR} stroke={FUR_LINE} strokeWidth="1.4" />
        <path d="M154 174 h16 M166 170 v10" stroke={FUR_LINE} strokeWidth="1.3" opacity=".8" />
      </g>

      {/* ---------------------------- desk ----------------------------- */}
      <g className="desk">
        <path d="M8 178 L232 178 L237 191 L3 191 Z" fill={DESK_TOP} />
        <rect x="3" y="189" width="234" height="56" rx="3" fill={DESK_FACE} />
        <rect x="3" y="189" width="234" height="4.5" fill={DESK_EDGE} />
        <path d="M22 232 H92 M22 240 H70 M152 232 H212" stroke="#4A3528" strokeWidth="1.8" strokeLinecap="round" opacity=".75" />
        {/* drawer, tucked into the right-hand side */}
        <rect x="180" y="200" width="46" height="30" rx="3" fill="#35251B" stroke={DESK_EDGE} strokeWidth="1.5" />
        <rect x="195" y="213" width="16" height="4.5" rx="2.2" fill="#8A6B52" />
      </g>

      {/* -------------------------- supplies --------------------------- */}
      <g className="supplies">
        <rect x="26" y="158" width="21" height="21" rx="3" fill={apron} />
        <path d="M47 163 C56 163 56 174 47 174" stroke={apron} strokeWidth="3.6" fill="none" />
        <rect x="26" y="158" width="21" height="4" rx="2" fill="#FFF" opacity=".3" />
        <rect x="186" y="160" width="17" height="19" rx="2.5" fill="#2F2822" />
        <path d="M190 160 L188 145" stroke="#C8553F" strokeWidth="3.2" strokeLinecap="round" />
        <path d="M195 160 L197 143" stroke="#4A85B9" strokeWidth="3.2" strokeLinecap="round" />
        <path d="M199 160 L202 148" stroke="#D9B35C" strokeWidth="3.2" strokeLinecap="round" />
      </g>

      {/* ------------------- name tag on the desk ---------------------- */}
      <g className="nametag">
        <rect x={tagX} y="200" width={tagW} height="28" rx="4" fill="#F8F4EB" stroke="#C6B9A4" strokeWidth="2" />
        <rect x={tagX} y="200" width={tagW} height="7.5" rx="3.7" fill={apron} />
        <text
          x="120"
          y="221"
          textAnchor="middle"
          fontSize={tagFont}
          fontWeight="700"
          letterSpacing=".5"
          fill="#30261E"
          fontFamily="Georgia, 'Times New Roman', serif"
        >
          {name}
        </text>
      </g>
    </svg>
  );
}
