export function formatScore(score: number): string {
	return (score * 100).toFixed(1);
}

export function formatPercent(value: number, digits = 1): string {
	return `${(value * 100).toFixed(digits)}%`;
}
