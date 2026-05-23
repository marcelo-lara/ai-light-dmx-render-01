const HEX_COLOR_LENGTH = 6;

function hexToRgbChannels(colorHex: string): [number, number, number] | null {
  const normalizedHex = colorHex.replace('#', '');
  if (normalizedHex.length !== HEX_COLOR_LENGTH) {
    return null;
  }

  const red = Number.parseInt(normalizedHex.slice(0, 2), 16);
  const green = Number.parseInt(normalizedHex.slice(2, 4), 16);
  const blue = Number.parseInt(normalizedHex.slice(4, 6), 16);

  if ([red, green, blue].some(Number.isNaN)) {
    return null;
  }

  return [red, green, blue];
}

export function getBeamOpacity(colorHex: string, intensity: number, maxOpacity: number): number {
  const channels = hexToRgbChannels(colorHex);
  const colorLevel = channels ? Math.max(...channels) / 255 : 1;
  const normalizedIntensity = Math.min(Math.max(intensity, 0), 1);

  return normalizedIntensity * colorLevel * maxOpacity;
}