export const formatValue = (value) => Intl.NumberFormat('zh-CN', {
  maximumSignificantDigits: 3,
  notation: 'compact',
}).format(Number.isFinite(Number(value)) ? Number(value) : 0);

export const formatThousands = (value) => Intl.NumberFormat('zh-CN', {
  maximumSignificantDigits: 3,
  notation: 'compact',
}).format(value);

export const getCssVariable = (variable, fallback = '') => {
  const val = getComputedStyle(document.documentElement).getPropertyValue(variable).trim()
  return val || fallback
};

const adjustHexOpacity = (hexColor, opacity) => {
  hexColor = hexColor.replace('#', '');
  const r = parseInt(hexColor.substring(0, 2), 16);
  const g = parseInt(hexColor.substring(2, 4), 16);
  const b = parseInt(hexColor.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
};

const adjustHSLOpacity = (hslColor, opacity) => {
  return hslColor.replace('hsl(', 'hsla(').replace(')', `, ${opacity})`);
};

const adjustOKLCHOpacity = (oklchColor, opacity) => {
  return oklchColor.replace(/oklch\((.*?)\)/, (match, p1) => `oklch(${p1} / ${opacity})`);
};

export const adjustColorOpacity = (color, opacity) => {
  if (!color || color === '') {
    return `rgba(107, 114, 128, ${opacity})`; // 默认灰色
  }
  if (color.startsWith('#')) {
    return adjustHexOpacity(color, opacity);
  } else if (color.startsWith('hsl')) {
    return adjustHSLOpacity(color, opacity);
  } else if (color.startsWith('oklch')) {
    return adjustOKLCHOpacity(color, opacity);
  } else {
    throw new Error('Unsupported color format');
  }
};

export const oklchToRGBA = (oklchColor) => {
  // Create a temporary div to use for color conversion
  const tempDiv = document.createElement('div');
  tempDiv.style.color = oklchColor;
  document.body.appendChild(tempDiv);
  
  // Get the computed style and convert to RGB
  const computedColor = window.getComputedStyle(tempDiv).color;
  document.body.removeChild(tempDiv);
  
  return computedColor;
};
