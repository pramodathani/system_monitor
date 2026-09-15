import { useState } from 'react';
import type { PointerEvent } from 'react';

import { Formatter } from '../utilities/formatter';

const PADDING = 4;

/** Props for Sparkline. */
interface SparklineProps {
  points: Array<[number, number]> | undefined;
  unit: string;
  label: string;
  width?: number;
  height?: number;
}

/**
 * A single-series trend line over the last fifteen minutes, with a hover readout.
 * @param props The points as [epoch seconds, value] pairs, the value's unit, and an accessible label.
 * @returns The sparkline, or a dash when there are fewer than two points.
 */
export function Sparkline(props: SparklineProps) {
  const { points, unit, label } = props;
  const width = props.width ?? 140;
  const height = props.height ?? 32;
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!points || points.length < 2) {
    return <span className="muted">—</span>;
  }

  const firstTime = points[0][0];
  const lastTime = points[points.length - 1][0];
  let maximum = 0;
  for (const point of points) {
    maximum = Math.max(maximum, point[1]);
  }
  const timeSpan = Math.max(1, lastTime - firstTime);
  const valueSpan = maximum > 0 ? maximum : 1;
  const plotWidth = width - PADDING * 2;
  const plotHeight = height - PADDING * 2;

  const xOf = (time: number) => PADDING + ((time - firstTime) / timeSpan) * plotWidth;
  const yOf = (value: number) => PADDING + plotHeight - (value / valueSpan) * plotHeight;

  const linePoints: string[] = [];
  for (const point of points) {
    linePoints.push(`${xOf(point[0]).toFixed(1)},${yOf(point[1]).toFixed(1)}`);
  }
  const baseline = PADDING + plotHeight;
  const areaPath = `M${xOf(firstTime).toFixed(1)},${baseline} L${linePoints.join(' L')} L${xOf(lastTime).toFixed(1)},${baseline} Z`;

  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const pointerX = ((event.clientX - bounds.left) / bounds.width) * width;
    let nearestIndex = 0;
    let nearestDistance = Number.POSITIVE_INFINITY;
    points.forEach((point, index) => {
      const distance = Math.abs(xOf(point[0]) - pointerX);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = index;
      }
    });
    setHoverIndex(nearestIndex);
  };

  const shownIndex = hoverIndex ?? points.length - 1;
  const shownPoint = points[shownIndex];
  const latest = points[points.length - 1];

  return (
    <span className="sparkline">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${label}: latest ${Formatter.number(latest[1])} ${unit}, peak ${Formatter.number(maximum)} ${unit} over the last ${Formatter.duration(timeSpan)}`}
        tabIndex={0}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setHoverIndex(null)}
        onFocus={() => setHoverIndex(points.length - 1)}
        onBlur={() => setHoverIndex(null)}
      >
        <path d={areaPath} className="sparkline-area" />
        <polyline points={linePoints.join(' ')} className="sparkline-line" />
        {hoverIndex !== null && (
          <line x1={xOf(shownPoint[0])} x2={xOf(shownPoint[0])} y1={PADDING} y2={baseline} className="sparkline-crosshair" />
        )}
        <circle cx={xOf(shownPoint[0])} cy={yOf(shownPoint[1])} r="4" className="sparkline-dot" />
      </svg>
      {hoverIndex !== null && (
        <span className="sparkline-tooltip" role="status">
          <strong>
            {Formatter.number(shownPoint[1])} {unit}
          </strong>
          <span className="muted">{Formatter.clockWithSeconds(shownPoint[0])}</span>
        </span>
      )}
    </span>
  );
}
