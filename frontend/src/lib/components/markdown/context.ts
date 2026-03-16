export const markdownRendererContextKey = Symbol('markdown-renderer');

export type MarkdownRendererContext = {
	getShowCopyButton: () => boolean;
	reportError: (error: Error) => void;
};
