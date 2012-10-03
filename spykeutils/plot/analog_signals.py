from __future__ import division

import scipy as sp
import quantities as pq

from guiqwt.builder import make
from guiqwt.baseplot import BasePlot
from guiqwt.plot import BaseCurveWidget

from ..spyke_exception import SpykeException
from .. import conversions
from ..progress_indicator import ProgressIndicator
from dialog import PlotDialog
import helper


@helper.needs_qt
def signals(signals, events=None, epochs=None, spike_trains=None,
           spikes=None, spike_train_waveforms = True,
           use_subplots=True,
           time_unit=pq.s, y_unit=None, progress=ProgressIndicator()):
    """ Create a plot from a list of AnalogSignal objects.

    :param list signals: The list of signals to plot.
    :param sequence events: A list of Event objects to be included in the
        plot.
    :param sequence epochs: A list of Epoch objects to be included in the
        plot.
    :param dict spike_trains: A dictionary of SpikeTrain objects to be
        included in the plot. Spikes are plotted as vertical lines.
        Indices of the dictionary (typically Unit objects) are used
        for color and legend entries.
    :param dict spikes: A dictionary of lists of Spike objects
        to be included in the plot. Waveforms of spikes are overlaid on
        the signal. Indices of the dictionary (typically Unit objects) are
        used for color and legend entries.
    :param bool spike_train_waveforms: Determines how the spike trains from
        ``spike_trains`` are used:

        * ``True``: Spikes from the SpikeTrain objects are plotted in the same
          way as the spikes from ``spike_waveforms``. Only works if waveform
          data is present in the SpikeTrain objects.
        * ``False``: Spikes are plotted as vertical lines.
          Indices of the dictionary (typically Unit objects) are used
          for color and legend entries.
    :param bool use_subplots: Determines if a separate subplot for is created
        each signal.
    :param Quantity time_unit: The unit of the x axis.
    :param progress: Set this parameter to report progress.
    :type progress: :class:`spykeutils.progress_indicator.ProgressIndicator`
    """
    if not signals:
        raise SpykeException(
            'Cannot create signal plot: No signal data provided!')

    # Plot title
    win_title = 'Analog Signal'
    if len(set((s.recordingchannel for s in signals))) == 1:
        if signals[0].recordingchannel.name:
            win_title += ' | Recording Channel: %s' %\
                         signals[0].recordingchannel.name
    if len(set((s.segment for s in signals))) == 1:
        if signals[0].segment.name:
            win_title += ' | Segment: %s' % signals[0].segment.name
    win = PlotDialog(toolbar=True, wintitle=win_title)

    if events is None:
        events = []
    if epochs is None:
        epochs = []
    if spike_trains is None:
        spike_trains = {}
    if spikes is None:
        spikes = {}

    if spike_train_waveforms:
        draw_spikes = []
        for st in spike_trains:
            draw_spikes.extend(conversions.spikes_from_spike_train(st))
    else:
        draw_spikes = spikes

    channels = range(len(signals))

    progress.set_ticks((len(draw_spikes) + len(spikes) + 1) * len(channels))

    # X-Axis
    sample = (1 / signals[0].sampling_rate).simplified
    x = sp.arange(signals[0].shape[0]) * sample
    x.units = time_unit

    offset = 0 * signals[0].units
    if use_subplots:
        plot = None
        for c in channels:
            pW = BaseCurveWidget(win)
            plot = pW.plot

            helper.add_epochs(plot, epochs, x.units)
            plot.add_item(make.curve(x, signals[c]))
            helper.add_events(plot, events, x.units)

            _add_spike_waveforms(plot, spikes, x.units, c, offset, progress)
            _add_spike_waveforms(plot, draw_spikes, x.units, c, offset,
                progress)

            if not spike_train_waveforms:
                for train in spike_trains:
                    color = helper.get_object_color(train.unit)
                    helper.add_spikes(plot, train, color, units=x.units)

            win.add_plot_widget(pW, c)
            plot.set_axis_unit(BasePlot.Y_LEFT,
                signals[c].dimensionality.string)
            progress.step()

        plot.set_axis_title(BasePlot.X_BOTTOM, 'Time')
        plot.set_axis_unit(BasePlot.X_BOTTOM, x.dimensionality.string)
    else:
        channels.reverse()

        pW = BaseCurveWidget(win)
        plot = pW.plot

        helper.add_epochs(plot, epochs, x.units)

        # Find plot y offset
        max_offset = 0 * signals[0].units
        for i, c in enumerate(channels[1:], 1):
            cur_offset = signals[channels[i - 1]].max() - signals[c].min()
            if cur_offset > max_offset:
                max_offset = cur_offset

        offset -= signals[channels[0]].min()

        for c in channels:
            plot.add_item(make.curve(x, signals[c] + offset))
            _add_spike_waveforms(plot, spikes, x.units, c, offset, progress)
            _add_spike_waveforms(plot, draw_spikes, x.units, c, offset,
                progress)
            offset += max_offset
            progress.step()

        helper.add_events(plot, events, x.units)

        if not spike_train_waveforms:
            for train in spike_trains:
                color = helper.get_object_color(train.unit)
                helper.add_spikes(plot, train, color, units=x.units)

        win.add_plot_widget(pW, 0)

        plot.set_axis_title(BasePlot.X_BOTTOM, 'Time')
        plot.set_axis_unit(BasePlot.X_BOTTOM, x.dimensionality.string)
        plot.set_axis_unit(BasePlot.Y_LEFT, signals[0].dimensionality.string)

    win.add_custom_curve_tools(False)

    units = set([s.unit for s in spike_trains])
    units = units.union([s.unit for s in spikes])

    progress.done()

    helper.make_window_legend(win, units, False)
    win.show()

    if use_subplots:
        win.add_x_synchronization_option(True, channels)
        win.add_y_synchronization_option(False, channels)


def _add_spike_waveforms(plot, spikes, x_units, channel, offset, progress):
    for spike in spikes:
        color = helper.get_object_color(spike.unit)
        # TODO: Is this usage of Spike.left_sweep correct?
        if spike.left_sweep:
            lsweep = spike.left_sweep
        else:
            lsweep = 0.0 * pq.ms
        start = (spike.time-lsweep).rescale(x_units)
        stop = (spike.waveform.shape[0] / spike.sampling_rate +
                spike.time - lsweep).rescale(x_units)
        spike_x = sp.arange(start, stop,
            (1.0 / spike.sampling_rate).rescale(x_units)) * x_units

        plot.add_item(make.curve(spike_x,
            spike.waveform[:, channel] + offset,
            color=color, linewidth=2))
        progress.step()