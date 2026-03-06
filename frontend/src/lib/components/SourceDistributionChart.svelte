<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	type Props = {
		distribution: Record<string, number>;
		title?: string;
		height?: number;
	};

	let { distribution, title, height = 200 }: Props = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart | null = null;

	const labels = Object.keys(distribution);
	const data = Object.values(distribution);

	function createChart() {
		if (chart) {
			chart.destroy();
		}

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		chart = new Chart(ctx, {
			type: 'doughnut',
			data: {
				labels: labels,
				datasets: [
					{
						data: data,
						backgroundColor: [
							'#2196f3',
							'#4caf50',
							'#ff9800',
							'#9c27b0',
							'#f44336',
							'#00bcd4',
							'#ffeb3b',
							'#795548',
							'#607d8b',
							'#8bc34a'
						],
						borderWidth: 2,
						borderColor: '#fff'
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						position: 'right',
						labels: {
							padding: 12,
							usePointStyle: true,
							font: { size: 11 },
							generateLabels: (chart) => {
								const data = chart.data;
								if (data.labels && data.datasets.length > 0) {
									const dataset = data.datasets[0];
									const total = dataset.data.reduce((a, b) => a + b, 0);
									return data.labels.map((label, i) => {
										const value = dataset.data[i];
										const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
										return {
											text: `${label}: ${value} (${percentage}%)`,
											fillStyle: dataset.backgroundColor[i],
											hidden: false,
											index: i
										};
									});
								}
								return [];
							}
						}
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
								const label = context.label || '';
								const value = context.parsed;
								const total = context.dataset.data.reduce((a, b) => a + b, 0);
								const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
								return `${label}: ${value} (${percentage}%)`;
							}
						}
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
		if (distribution && canvas) {
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
