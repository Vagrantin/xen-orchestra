import _ from 'intl'
import ActionButton from 'action-button'
import Component from 'base-component'
import React from 'react'
import { checkXoaHlUpdate, getXoaHlUpdateProgress, getXoaHlUpdateStatus, startXoaHlUpdate } from 'xo'

// ===================================================================

export default class XoaHlUpdates extends Component {
  constructor(props) {
    super(props)
    this.state = {
      checking: false,
      updateAvailable: false,
      packages: [],
      updating: false,
      log: [],
    }
  }

  _checkForUpdate = async () => {
    this.setState({ checking: true })
    await checkXoaHlUpdate()
    const { updateAvailable, packages } = await getXoaHlUpdateStatus()
    this.setState({ checking: false, updateAvailable, packages })
  }

  _startUpdate = async () => {
    this.setState({ updating: true })
    await startXoaHlUpdate()
    const { log } = await getXoaHlUpdateProgress()
    this.setState({ updating: false, log })
  }

  render() {
    const { checking, updateAvailable, packages, log } = this.state

    return (
      <div>
        <ActionButton btnStyle='info' handler={this._checkForUpdate} icon='refresh' pending={checking}>
          {_('xoaHlCheckForUpdate')}
        </ActionButton>{' '}
        <ActionButton btnStyle='success' disabled={!updateAvailable} handler={this._startUpdate} icon='upgrade'>
          {_('xoaHlStartUpdate')}
        </ActionButton>
        {updateAvailable && packages.length > 0 ? (
          <div>
            <p>{_('xoaHlPackagesAvailable')}</p>
            <table className='table'>
              <thead>
                <tr>
                  <th>{_('xoaHlPackageName')}</th>
                  <th>{_('xoaHlPackageVersion')}</th>
                </tr>
              </thead>
              <tbody>
                {packages.map(({ name, version }) => (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>{_('xoaHlUpToDate')}</p>
        )}
        {log.length > 0 && (
          <div>
            <hr />
            <pre className='overflow-auto' style={{ maxHeight: '20em' }}>
              {log.join('\n')}
            </pre>
          </div>
        )}
      </div>
    )
  }
}
