const INDIA_TIME_ZONE = 'Asia/Kolkata';

const clockFormat = new Intl.DateTimeFormat('en-IN', {
  timeZone: INDIA_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const clockWithSecondsFormat = new Intl.DateTimeFormat('en-IN', {
  timeZone: INDIA_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

const dayAndMonthFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: INDIA_TIME_ZONE,
  day: '2-digit',
  month: 'numeric',
});

const MONTH_NAMES = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

const dayKeyFormat = new Intl.DateTimeFormat('en-CA', {
  timeZone: INDIA_TIME_ZONE,
});

const numberFormat = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 1,
});

/** Formats durations, India times and numbers for display. */
export class Formatter {
  /**
   * Describes a length of time in its two largest units.
   * @param seconds The length of time.
   * @returns Text such as "45 s", "3 min 15 s" or "2 h 5 min".
   */
  static duration(seconds: number): string {
    const wholeSeconds = Math.max(0, Math.floor(seconds));
    if (wholeSeconds < 60) {
      return `${wholeSeconds} s`;
    }
    const minutes = Math.floor(wholeSeconds / 60);
    const remainingSeconds = wholeSeconds % 60;
    if (minutes < 60) {
      return remainingSeconds === 0 ? `${minutes} min` : `${minutes} min ${remainingSeconds} s`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    if (hours < 24) {
      return `${hours} h ${remainingMinutes} min`;
    }
    const days = Math.floor(hours / 24);
    return `${days} d ${hours % 24} h`;
  }

  /**
   * Describes a moment in India time, adding the date when it is not today.
   * @param epochSeconds The moment.
   * @param nowSeconds The current time, to decide whether the moment is today.
   * @returns Text such as "08:30" or "14 Sep 08:30".
   */
  static indiaTime(epochSeconds: number, nowSeconds: number): string {
    const moment = new Date(epochSeconds * 1000);
    const today = dayKeyFormat.format(new Date(nowSeconds * 1000));
    const clock = clockFormat.format(moment);
    if (dayKeyFormat.format(moment) === today) {
      return clock;
    }
    return `${Formatter.dayAndMonth(moment)} ${clock}`;
  }

  /**
   * Writes a date as a two-digit day and a three-letter month, matching the server's messages.
   * @param moment The moment.
   * @returns Text such as "14 Sep".
   */
  static dayAndMonth(moment: Date): string {
    let day = '';
    let monthNumber = 1;
    for (const part of dayAndMonthFormat.formatToParts(moment)) {
      if (part.type === 'day') {
        day = part.value;
      } else if (part.type === 'month') {
        monthNumber = Number(part.value);
      }
    }
    return `${day} ${MONTH_NAMES[monthNumber - 1]}`;
  }

  /**
   * Formats a moment as an India clock time with seconds.
   * @param epochSeconds The moment.
   * @returns Text such as "15:17:08".
   */
  static clockWithSeconds(epochSeconds: number): string {
    return clockWithSecondsFormat.format(new Date(epochSeconds * 1000));
  }

  /**
   * Formats a number with Indian digit grouping and at most one decimal.
   * @param value The number.
   * @returns The formatted number.
   */
  static number(value: number): string {
    return numberFormat.format(value);
  }

  /**
   * Reads a detail value that should be a number.
   * @param value The raw detail value.
   * @returns The number, or null.
   */
  static asNumber(value: unknown): number | null {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }

  /**
   * Reads a detail value that should be text.
   * @param value The raw detail value.
   * @returns The text, or an empty string.
   */
  static asText(value: unknown): string {
    if (value === null || value === undefined) {
      return '';
    }
    return String(value);
  }
}
