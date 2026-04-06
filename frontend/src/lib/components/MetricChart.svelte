<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	type Props = {
		type?: 'line' | 'bar';
		data: {
			labels: string[];
			datasets: {
				label: string;
				data: number[];
				borderColor?: string | string[];
				backgroundColor?: string | string[];
			}[];
		};
		title?: string;
		height?: number;
	};

	let { type = 'line', data, title, height = 250 }: Props = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart | null = null;

	function createChart() {
		if (chart) {
			chart.destroy();
		}

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		chart = new Chart(ctx, {
			type,
			data: {
				labels: data.labels,
				datasets: data.datasets.map((ds, i) => ({
					...ds,
					borderColor: ds.borderColor || getDefaultColor(i),
					backgroundColor: ds.backgroundColor || getDefaultColor(i, 0.2),
					fill: type === 'line',
					tension: 0.3,
					pointRadius: 4,
					pointHoverRadius: 6
				}))
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						position: 'bottom',
						labels: {
							padding: 20,
							usePointStyle: true
						}
					},
					title: title ? {
						display: true,
						text: title,
						font: { size: 14, weight: 'bold' as const },
						padding: { bottom: 20 }
					} : undefined
				},
				scales: type === 'line' ? {
					y: {
						beginAtZero: true,
						grid: { color: '#f0f0f0' }
					},
					x: {
						grid: { display: false }
					}
				} : {
					y: {
						beginAtZero: true,
						grid: { color: '#f0f0f0' }
					},
					x: {
						grid: { display: false }
					}
				},
				interaction: {
					intersect: false,
					mode: 'index'
				}
			}
		});
	}

	function getDefaultColor(index: number, alpha = 1): string {
		const colors = [
			`rgba(59, 130, 246, ${alpha})`,
			`rgba(16, 185, 129, ${alpha})`,
			`rgba(245, 158, 11, ${alpha})`,
			`rgba(239, 68, 68, ${alpha})`,
			`rgba(139, 92, 246, ${alpha})`,
			`rgba(236, 72, 153, ${alpha})`
		];
		return colors[index % colors.length];
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
		if (data && canvas) {
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
