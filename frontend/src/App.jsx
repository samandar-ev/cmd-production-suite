import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { useAuth, isManager } from './lib/auth';
import { ConfirmHost, Spinner, ToastHost } from './ui';
import Shell from './shell/Shell';
import { tr } from './lib/i18n';

const page = load => lazy(load);
const SignIn = page(() => import('./pages/SignIn'));
const Today = page(() => import('./pages/Today'));
const MyWork = page(() => import('./pages/MyWork'));
const Production = page(() => import('./pages/Production'));
const ContentPage = page(() => import('./pages/ContentPage'));
const OrderPage = page(() => import('./pages/OrderPage'));
const Review = page(() => import('./pages/Review'));
const ReviewItem = page(() => import('./pages/ReviewItem'));
const Projects = page(() => import('./pages/Projects'));
const ProjectPage = page(() => import('./pages/ProjectPage'));
const Clients = page(() => import('./pages/Clients'));
const Calendar = page(() => import('./pages/Calendar'));
const Messages = page(() => import('./pages/Messages'));
const Workspace = page(() => import('./pages/Workspace'));
const Money = page(() => import('./pages/Money'));
const Reports = page(() => import('./pages/Reports'));
const Team = page(() => import('./pages/Team'));
const Contracts = page(() => import('./pages/Contracts'));
const Settings = page(() => import('./pages/Settings'));
const Approvals = page(() => import('./pages/Approvals'));

function Guard({ children, managers = false, owner = false }) {
  const { user, ready } = useAuth();
  const { pathname } = useLocation();
  if (!ready) return <Spinner label={tr('Opening CMD')} />;
  if (!user) return <Navigate to="/sign-in" replace state={{ from: pathname }} />;
  if ((managers && !isManager(user)) || (owner && user.role !== 'OWNER')) return <Navigate to="/" replace />;
  return children;
}

const M = ({ children }) => <Guard managers>{children}</Guard>;
const O = ({ children }) => <Guard owner>{children}</Guard>;

const Old = ({ to }) => {
  const { id } = useParams();
  return <Navigate to={to.replace(':id', id)} replace />;
};
const V1 = [
  ['videos/:id', '/review/:id'],
  ['orders/projects/:id', '/projects/:id'],
  ['finance', '/money'],
  ['ai-approvals', '/approvals'],
  ['content', '/production'],
];

function Home() {
  const user = useAuth(s => s.user);
  return isManager(user) ? <Today /> : <MyWork />;
}

export default function App() {
  const load = useAuth(s => s.load);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <BrowserRouter>
      <ToastHost>
        <ConfirmHost>
          <Suspense fallback={<Spinner />}>
            <Routes>
              <Route path="/sign-in" element={<SignIn />} />
              <Route path="/login" element={<Navigate to="/sign-in" replace />} />
              {V1.map(([from, to]) => (
                <Route key={from} path={from} element={<Old to={to} />} />
              ))}
              <Route
                element={
                  <Guard>
                    <Shell />
                  </Guard>
                }
              >
                <Route index element={<Home />} />
                <Route
                  path="production"
                  element={
                    <M>
                      <Production />
                    </M>
                  }
                />
                <Route
                  path="content/:id"
                  element={
                    <M>
                      <ContentPage />
                    </M>
                  }
                />
                <Route path="orders/:id" element={<OrderPage />} />
                <Route
                  path="review"
                  element={
                    <M>
                      <Review />
                    </M>
                  }
                />
                <Route path="review/:id" element={<ReviewItem />} />
                <Route path="projects" element={<Projects />} />
                <Route path="projects/:id" element={<ProjectPage />} />
                <Route
                  path="clients"
                  element={
                    <M>
                      <Clients />
                    </M>
                  }
                />
                <Route path="calendar" element={<Calendar />} />
                <Route path="messages" element={<Messages />} />
                <Route path="messages/:taskId" element={<Messages />} />
                <Route path="workspace" element={<Workspace />} />
                <Route
                  path="money"
                  element={
                    <O>
                      <Money />
                    </O>
                  }
                />
                <Route
                  path="reports"
                  element={
                    <O>
                      <Reports />
                    </O>
                  }
                />
                <Route
                  path="team"
                  element={
                    <O>
                      <Team />
                    </O>
                  }
                />
                <Route
                  path="contracts"
                  element={
                    <O>
                      <Contracts />
                    </O>
                  }
                />
                <Route path="settings" element={<Settings />} />
                <Route
                  path="approvals"
                  element={
                    <M>
                      <Approvals />
                    </M>
                  }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </ConfirmHost>
      </ToastHost>
    </BrowserRouter>
  );
}
