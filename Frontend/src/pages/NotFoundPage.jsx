import { Link } from 'react-router'
import { Empty } from '../components.jsx'

export default function NotFoundPage() {
  return (
    <div className="wrap">
      <Empty title="This page does not exist">
        <p>The link may be old or mistyped.</p>
        <div className="inline-actions">
          <Link to="/">Go to the home page</Link>
          <Link to="/search">Search schemes</Link>
        </div>
      </Empty>
    </div>
  )
}
