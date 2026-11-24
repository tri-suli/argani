import Alpine from 'alpinejs';
import { FetchBoardClient } from './board/board-client';
import { BoardPoller } from './board/board-poller';
import { FetchTaskClient } from './board/task-client';
import { createDashboard } from './components/dashboard';
import './styles.css';

const fetchFunction = (url: string, init: RequestInit) => fetch(url, init);
const boardClient = new FetchBoardClient(fetchFunction, '/api/board');
const taskClient = new FetchTaskClient(fetchFunction, '/api/tasks');
const poller = new BoardPoller(boardClient, taskClient);

Alpine.data('dashboard', () => createDashboard({ poller, taskClient, now: () => new Date() }));
Alpine.start();
