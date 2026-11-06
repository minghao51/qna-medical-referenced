/**
 * Minimal buffered SSE decoder for the current chat contract.
 *
 * Handles UTF-8 split across chunks, CRLF/LF frame boundaries, multi-line
 * `data:` fields and EOF without inventing a terminal event.
 */
export class SseDecoder {
	private buffer = '';
	private decoder = new TextDecoder();
	private finished = false;

	push(chunk: Uint8Array): string[] {
		if (this.finished) throw new Error('SSE decoder already finished');
		this.buffer += this.decoder.decode(chunk, { stream: true });
		return this.extract(false);
	}

	finish(): string[] {
		if (this.finished) return [];
		this.finished = true;
		this.buffer += this.decoder.decode();
		return this.extract(true);
	}

	private extract(flush: boolean): string[] {
		// Normalising per call is safe: a trailing \r from a split CRLF becomes
		// \n and the next chunk begins with \n, producing the same blank line.
		this.buffer = this.buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
		const frames: string[] = [];
		let boundary = this.buffer.indexOf('\n\n');
		while (boundary >= 0) {
			const raw = this.buffer.slice(0, boundary);
			this.buffer = this.buffer.slice(boundary + 2);
			const data = this.parseFrame(raw);
			if (data !== null) frames.push(data);
			boundary = this.buffer.indexOf('\n\n');
		}
		if (flush && this.buffer.trim()) {
			const data = this.parseFrame(this.buffer);
			this.buffer = '';
			if (data !== null) frames.push(data);
		}
		return frames;
	}

	private parseFrame(raw: string): string | null {
		const dataLines: string[] = [];
		for (const line of raw.split('\n')) {
			if (line.startsWith('data:')) {
				dataLines.push(line.slice(5).replace(/^ /, ''));
			}
		}
		return dataLines.length ? dataLines.join('\n') : null;
	}
}

export type StreamOutcome = 'complete' | 'error' | 'incomplete';

/** Classify buffered data frames by their explicit terminal event only. */
export function classifyStreamOutcome(dataFrames: string[]): StreamOutcome {
	let outcome: StreamOutcome = 'incomplete';
	for (const frame of dataFrames) {
		let payload: unknown;
		try {
			payload = JSON.parse(frame);
		} catch {
			continue;
		}
		if (!payload || typeof payload !== 'object') continue;
		const event = payload as { done?: unknown; error?: unknown };
		if (event.done === true) {
			outcome = event.error ? 'error' : 'complete';
		}
	}
	return outcome;
}
