import time
import struct
import corr
import argparse
import sys
import numpy as np
import cPickle as pickle

NCHANS = 512
ADC_CLK = 250e6

def get_data(r, visibilities):
    """
    Return a dictionary of numpy data arrays, which may or may not be complex
    """
    rv = {}
    for vis in visibilities:
        if len(vis) != 2:
            print 'Trying to grab visibility %s, which makes no sense' % vis
            exit()
        elif vis[0] == vis[1]:
            auto = True
        else:
            auto = False

        if auto:
            d = np.fromstring(r.read('xengine12_muxed_%s_real' % vis, 4*NCHANS), dtype='>i4')
        else:
            d_r = np.fromstring(r.read('xengine12_muxed_%s_real' % vis, 4*NCHANS), dtype='>i4')
            d_i = np.fromstring(r.read('xengine12_muxed_%s_imag' % vis, 4*NCHANS), dtype='>i4')
            d = d_r + 1j* d_i
        rv[vis] = d
    return rv

def write_file(d, t, prefix='dat_poco_snap_simple'):
    fname = prefix + '-%s.pkl' % time.time()
    print 'Writing %s' % fname,
    t0 = time.time()
    with open(fname, 'w') as fh:
        pickle.dump({'data': d, 'times': t}, fh)
    t1 = time.time()
    print 'Done in %.2f seconds' % (t1-t0)
        

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--prog', action='store_true', default=False,
                        help='Use this flag to programthe FPGA (THIS SCRIPT DOES NOT DO ADC CALIBRATION)')
    parser.add_argument('-b', '--boffile', default='spoco12_100_2017-03-17_1809.bof',
                        help='Which boffile to program')
    parser.add_argument('-f', '--fftshift', type=int, default=0xffff,
                        help='FFT shift schedule as an integer. Default:0xffff')
    parser.add_argument('-e', '--eq', type=int, default=100,
                        help='EQ value, which is applied to all inputs/channels. Default:100')
    parser.add_argument('-a', '--acc_len', type=int, default=2**20,
                        help='Number of spectra to accumulate. Default:2^20')
    parser.add_argument('-v', '--visibilities', default='aa,bb,ab',
                        help='Comma separated list of visibilities to grab. Default:aa,bb,ab')
    parser.add_argument('-t', '--filetime', type=int, default=600,
                        help='Time in seconds of each data file. Default:600')
    parser.add_argument('-s', '--snap', default='10.10.10.101',
                        help='SNAP hostname of IP. Default:10.10.10.101')

    opts = parser.parse_args()


    #if len(args) == 0:
    #    print 'No SNAP hostname given. Usage: poco_snap_simple.py [options] <katcp_host>'

    print 'Connecting to %s' % opts.snap
    r = corr.katcp_wrapper.FpgaClient(opts.snap)
    time.sleep(0.05)

    if r.is_connected():
        print 'Connected!'
    else:
        print 'Failed to Connect!'
        exit()

    if opts.prog:
        print 'Trying to program with boffile %s' % opts.boffile
        if opts.boffile in r.listbof():
            r.progdev(opts.boffile)
            print 'done'
        else:
            print 'boffile %s does not exist on server!' % opts.boffile
            exit()

    print 'FPGA board clock is', r.est_brd_clk()

    # Configure registers
    print 'Setting FFT shift to %x' % opts.fftshift
    r.write_int('ctrl_sw', opts.fftshift & 0xffff)

    # Input MUX defaults to ADC data (other options are PRNG and custom TVG)
    # Input delays default to zero
    # Don't care about PRNG seeds, since we're not using the noise vectors

    # Set all the EG gains to the same value. Be careful of input numbering, the simulink diagram
    # looks suspicious, but maybe there's an intentional re-labeling
    print 'Setting all EQ values to %d' % opts.eq
    for i in range(6):
        eq_vec = [opts.eq] * NCHANS
        r.write('eq_%d_%d_coeffs' % (2*i, 2*i+1), struct.pack('>%dL' % NCHANS, *eq_vec))
    

    print 'Setting accumulation length to %d spectra' % opts.acc_len,
    print '(%.2f seconds)' % (opts.acc_len * NCHANS / ADC_CLK)
    r.write_int('acc_length', opts.acc_len * NCHANS)

    print 'Triggering sync'
    r.write_int('Sync_sync_pulse', 0)
    r.write_int('Sync_sync_sel', 1)
    r.write_int('Sync_sync_pulse', 1)
    trig_time = time.time()
    r.write_int('Sync_sync_pulse', 0)

    this_acc = 1
    this_acc_time = trig_time
    file_start_time = time.time()
    data  = []
    times = []
    while(True):
        try:
            latest_acc = r.read_int('acc_num')
            latest_acc_time = time.time()
            if latest_acc == this_acc:
                time.sleep(0.05)
            elif latest_acc == this_acc + 1:
                print 'Got accumulation after %.2f seconds' % (latest_acc_time - this_acc_time)
                data  += [get_data(r, [vis for vis in opts.visibilities.split(',')])]
                times += [latest_acc_time]
                this_acc = latest_acc
                this_acc_time = latest_acc_time
                if time.time() > (file_start_time + opts.filetime):
                    write_file(data, times)
                    file_start_time = time.time()
                    data  = []
                    times = []
            else:
                print 'Last accumulation was number %d' % this_acc,
                print 'Next accumulation is number %d' % latest_acc,
                print 'Bad!'
                this_acc = latest_acc
                this_acc_time = latest_acc_time
        except KeyboardInterrupt:
            'Exiting'
            write_file(data, times)
            exit()
            




