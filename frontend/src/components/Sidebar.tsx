import { useState } from 'react';
import type { Fixture } from '../hooks/useFixtures';

type SendFn = (id: string, metaKey: string, value: string | number | number[]) => void;

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

function hexToRgb(hex: string): [number, number, number] {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const S = {
  sidebar: {
    width: 232,
    minWidth: 232,
    height: '100%',
    overflowY: 'auto' as const,
    background: '#0b0b14',
    borderLeft: '1px solid #1b1b2e',
    display: 'flex',
    flexDirection: 'column' as const,
    fontFamily: 'monospace',
    fontSize: 11,
    color: '#9999cc',
  },
  section: {
    padding: '12px 12px 4px',
  },
  sectionTitle: {
    textTransform: 'uppercase' as const,
    letterSpacing: '0.12em',
    fontSize: 10,
    color: '#3f3f6a',
    marginBottom: 8,
  },
  divider: {
    borderBottom: '1px solid #16162a',
    margin: '4px 0',
  },
  row: {
    padding: '8px 12px 10px',
    borderBottom: '1px solid #111122',
  },
  fixtureName: {
    color: '#bbbbee',
    marginBottom: 6,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  control: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginTop: 4,
  },
  label: {
    color: '#55557a',
    width: 36,
    flexShrink: 0,
  },
  slider: {
    flex: 1,
    accentColor: '#4466cc',
    cursor: 'pointer',
    height: 3,
  },
  valueText: {
    color: '#5566aa',
    width: 34,
    textAlign: 'right' as const,
    flexShrink: 0,
  },
  select: {
    flex: 1,
    background: '#14142a',
    border: '1px solid #2a2a44',
    borderRadius: 3,
    color: '#aaaadd',
    padding: '2px 4px',
    fontFamily: 'monospace',
    fontSize: 11,
    cursor: 'pointer',
    outline: 'none',
  },
  colorInput: {
    width: 40,
    height: 22,
    padding: 1,
    border: '1px solid #2a2a44',
    borderRadius: 3,
    background: '#14142a',
    cursor: 'pointer',
  },
  empty: {
    padding: '12px',
    color: '#333355',
    fontStyle: 'italic' as const,
  },
};

// ---------------------------------------------------------------------------
// Moving-head row
// ---------------------------------------------------------------------------

function MovingHeadRow({ fixture, send }: { fixture: Fixture; send: SendFn }) {
  const [dim, setDim] = useState(Math.round(fixture.intensity * 255));
  const [colorLabel, setColorLabel] = useState(
    fixture.color_wheel_current ?? fixture.color_wheel_options?.[0] ?? 'White'
  );

  return (
    <div style={S.row}>
      <div style={S.fixtureName}>{fixture.name}</div>

      <div style={S.control}>
        <span style={S.label}>dim</span>
        <input
          type="range"
          min={0}
          max={255}
          value={dim}
          style={S.slider}
          onChange={(e) => {
            const v = Number(e.target.value);
            setDim(v);
            send(fixture.id, 'dim', v);
          }}
        />
        <span style={S.valueText}>{Math.round(dim / 2.55)}%</span>
      </div>

      <div style={S.control}>
        <span style={S.label}>color</span>
        <select
          value={colorLabel}
          style={S.select}
          onChange={(e) => {
            setColorLabel(e.target.value);
            send(fixture.id, 'color', e.target.value);
          }}
        >
          {(fixture.color_wheel_options ?? []).map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Par-can row
// ---------------------------------------------------------------------------

function ParCanRow({ fixture, send }: { fixture: Fixture; send: SendFn }) {
  // Default to white when fixture starts black (pre-show / unset state)
  const [color, setColor] = useState(
    fixture.color_hex === '#000000' || fixture.color_hex === '#000000'.toUpperCase()
      ? '#ffffff'
      : fixture.color_hex.toLowerCase()
  );

  return (
    <div style={S.row}>
      <div style={S.fixtureName}>{fixture.name}</div>

      <div style={S.control}>
        <span style={S.label}>color</span>
        <input
          type="color"
          value={color}
          style={S.colorInput}
          onChange={(e) => {
            setColor(e.target.value);
            send(fixture.id, 'rgb', hexToRgb(e.target.value));
          }}
        />
        <span style={{ ...S.valueText, flex: 1, textAlign: 'left' }}>{color.toUpperCase()}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

interface Props {
  movingHeads: Fixture[];
  parcans: Fixture[];
  sendFixtureCommand: SendFn;
}

export function Sidebar({ movingHeads, parcans, sendFixtureCommand }: Props) {
  return (
    <div style={S.sidebar}>

      <div style={S.section}>
        <div style={S.sectionTitle}>Moving Heads</div>
      </div>

      {movingHeads.length === 0 ? (
        <div style={S.empty}>no fixtures</div>
      ) : (
        movingHeads.map((f) => (
          <MovingHeadRow key={f.id} fixture={f} send={sendFixtureCommand} />
        ))
      )}

      <div style={{ ...S.section, marginTop: 8 }}>
        <div style={S.sectionTitle}>Par Cans</div>
      </div>

      {parcans.length === 0 ? (
        <div style={S.empty}>no fixtures</div>
      ) : (
        parcans.map((f) => (
          <ParCanRow key={f.id} fixture={f} send={sendFixtureCommand} />
        ))
      )}

    </div>
  );
}
