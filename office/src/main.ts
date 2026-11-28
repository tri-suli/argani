import Alpine from 'alpinejs';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import FetchBoardClient from '@/board/board-client';
import BoardPoller from '@/board/board-poller';
import BoardView from '@/board/board-view';
import DiffRows from '@/board/diff-rows';
import FileTree from '@/board/file-tree';
import HashNavigation from '@/board/hash-navigation';
import HistorySteps from '@/board/history-steps';
import addLinkHook from '@/board/link-hook';
import MarkdownRenderer from '@/board/markdown-renderer';
import RoundOverview from '@/board/round-overview';
import createBrowserReaderEnvironment from '@/board/reader-environment';
import FetchTaskClient from '@/board/task-client';
import createDashboard from '@/components/dashboard';
import '@fontsource/ibm-plex-mono/latin-400.css';
import '@fontsource/ibm-plex-mono/latin-500.css';
import '@fontsource/ibm-plex-mono/latin-600.css';
import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-sans/latin-600.css';
import '@fontsource/ibm-plex-sans/latin-700.css';
import 'material-symbols/outlined.css';
import '@/styles.css';

const fetchFunction = (url: string, init: RequestInit) => fetch(url, init);

const boardClient = new FetchBoardClient(fetchFunction, '/api/board');

const taskClient = new FetchTaskClient(fetchFunction, '/api/tasks');

const poller = new BoardPoller(boardClient, taskClient);

const boardView = new BoardView();

const historySteps = new HistorySteps();

const fileTree = new FileTree();

const navigation = new HashNavigation(window);

// navigator.clipboard is only read when Copy is pressed, so a page without a clipboard still loads
const clipboard = { writeText: (text: string) => navigator.clipboard.writeText(text) };

const purify = DOMPurify(window);

addLinkHook(purify);

const markdownRenderer = new MarkdownRenderer(purify, marked);

Alpine.data('dashboard', () => createDashboard({ poller, taskClient, boardView, historySteps, fileTree, roundOverview: new RoundOverview(markdownRenderer), navigation, markdownRenderer, diffRows: new DiffRows(), readerEnvironment: createBrowserReaderEnvironment(window), clipboard, now: () => new Date() }));

Alpine.start();
