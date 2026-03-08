<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	type Props = {
		breakdown: Record<string, { hit_rate?: number; mrr?: number; count: number }>;
		metric?: 'hit_rate' | 'mrr';
		title?: string;
		height?: number;
	};

	let { breakdown, metric = 'hit_rate', title, height = 250 }: Props = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart | null = null;

	function createChart() {
		if (chart) {
			chart.destroy();
		}

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const categories = Object.entries(breakdown).sort((a, b) => b[1].count - a[1].count);
		const labels = categories.map(([category]) => category);
		const values = categories.map(([, data]) => (data[metric] || 0) * 100);
		const counts = categories.map(([, data]) => data.count);

		chart = new Chart(ctx, {
			type: 'bar',
			data: {
				labels: labels,
				datasets: [
					{
						label: metric === 'hit_rate' ? 'Hit Rate %' : 'MRR %',
						data: values,
						backgroundColor: values.map((v) =>
							v >= 70 ? '#4caf50' : v >= 40 ? '#ff9800' : '#f44336'
						),
						borderRadius: 4
					}
				]
			},
			options: {
				indexAxis: 'y' as const,
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						display: false
					},
					title: title
						? {
								display: true,
								text: title,
								font: { size: 14, weight: 'bold' as const },
								padding: { bottom: 12 }
							}
						: undefined,
					tooltip: {
						callbacks: {
							label: (context) => {
								const idx = context.dataIndex;
								const value = Number(context.parsed.x ?? 0);
								const count = counts[idx] ?? 0;
								return `${metric === 'hit_rate' ? 'Hit Rate' : 'MRR'}: ${value.toFixed(1)}% (n=${count})`;
							}
						}
					}
				},
				scales: {
					x: {
						beginAtZero: true,
						max: 100,
						title: {
							display: true,
							text: metric === 'hit_rate' ? 'Hit Rate (%)' : 'MRR (%)'
						},
						grid: { color: '#f0f0f0' }
					},
					y: {
						grid: { display: false }
					}
				}
			}
		});
	}

	onMount(() => {
		createChart();
	});

	onDestroy(() => {
		if (chart) {
			chart.destroy();
		}
	});

	$effect(() => {
		if (breakdown && canvas) {
			createChart();
		}
	});
</script>

<div class="chart-container" style="height: {height}px">
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.chart-container {
		position: relative;
		width: 100%;
	}
</style>
