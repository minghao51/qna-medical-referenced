import type { EvaluationResponse } from '$lib/types';

export async function exportToCSV(data: EvaluationResponse, filename?: string): Promise<void> {
	const rows: Array<{ stage: string; metric: string; value: string | number }> = [];

	// Flatten summary metrics
	if (data.summary) {
		rows.push({ stage: 'summary', metric: 'run_dir', value: data.run_dir });
		rows.push({ stage: 'summary', metric: 'duration_s', value: data.summary.duration_s });
		rows.push({ stage: 'summary', metric: 'status', value: data.summary.status });
		rows.push({ stage: 'summary', metric: 'failed_thresholds_count', value: data.summary.failed_thresholds_count });
	}

	// Flatten retrieval metrics
	if (data.retrieval_metrics) {
		const rm = data.retrieval_metrics;
		for (const [key, value] of Object.entries(rm)) {
			if (typeof value === 'number') {
				rows.push({ stage: 'retrieval', metric: key, value: value.toFixed(4) });
			}
		}
	}

	// Flatten step metrics
	if (data.step_metrics) {
		for (const [stage, metrics] of Object.entries(data.step_metrics)) {
			const agg = metrics.aggregate || {};
			for (const [key, value] of Object.entries(agg)) {
				if (typeof value === 'number') {
					rows.push({ stage, metric: key, value: value.toFixed(4) });
				} else if (typeof value === 'boolean') {
					rows.push({ stage, metric: key, value: value ? 'true' : 'false' });
				} else if (typeof value === 'string') {
					rows.push({ stage, metric: key, value: `"${value}"` });
				} else if (typeof value === 'object') {
					rows.push({ stage, metric: key, value: JSON.stringify(value) });
				}
			}
		}
	}

	// Convert to CSV
	const headers = ['stage', 'metric', 'value'];
	const csvContent = [
		headers.join(','),
		...rows.map((row) => headers.map((h) => row[h as keyof typeof row]).join(','))
	].join('\n');

	// Download
	const blob = new Blob([csvContent], { type: 'text/csv' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename || `evaluation-${data.run_dir}.csv`;
	a.click();
	URL.revokeObjectURL(url);
}

export async function exportToJSON(data: EvaluationResponse, filename?: string): Promise<void> {
	const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename || `evaluation-${data.run_dir}.json`;
	a.click();
	URL.revokeObjectURL(url);
}

export async function exportCharts(): Promise<void> {
	// Find all canvas elements in charts
	const canvases = document.querySelectorAll('.chart-card canvas, .data-quality-section canvas');
	let index = 0;

	for (const canvas of canvases) {
		try {
			const dataUrl = (canvas as HTMLCanvasElement).toDataURL('image/png');
			const a = document.createElement('a');
			a.href = dataUrl;

			// Try to get a meaningful filename from parent elements
			let chartName = `chart-${index}`;
			const parent = canvas.closest('.chart-card');
			const titleElement = parent?.querySelector('h3, h4');
			if (titleElement) {
				chartName = titleElement.textContent?.toLowerCase().replace(/\s+/g, '-') || chartName;
			}

			a.download = `${chartName}.png`;
			a.click();
			index++;
		} catch (e) {
			console.error('Failed to export chart:', e);
		}
	}
}

export function downloadBlob(content: string, filename: string, mimeType: string): void {
	const blob = new Blob([content], { type: mimeType });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}
