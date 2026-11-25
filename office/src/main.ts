import Alpine from 'alpinejs';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import FetchBoardClient from '@/board/board-client';
import BoardPoller from '@/board/board-poller';
import BoardView from '@/board/board-view';
import addLinkHook from '@/board/link-hook';
import MarkdownRenderer from '@/board/markdown-renderer';
import FetchTaskClient from '@/board/task-client';
import createDashboard from '@/components/dashboard';
import '@/styles.css';

const fetchFunction = (url: string, init: RequestInit) => fetch(url, init);

const boardClient = new FetchBoardClient(fetchFunction, '/api/board');

const taskClient = new FetchTaskClient(fetchFunction, '/api/tasks');

const poller = new BoardPoller(boardClient, taskClient);

const boardView = new BoardView();

const purify = DOMPurify(window);

addLinkHook(purify);

const markdownRenderer = new MarkdownRenderer(purify, marked);

Alpine.data('dashboard', () => createDashboard({ poller, taskClient, boardView, markdownRenderer, now: () => new Date() }));

Alpine.start();
