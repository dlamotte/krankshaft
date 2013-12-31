module.exports = function(config) {
  config.set({
    basePath: '',
    browsers: ['PhantomJS'],
    coverageReporter: {
      type: 'lcov',
      dir: 'coverage/'
    },
    files: [
      'lib/jquery.js',
      'lib/underscore.js',
      'lib/backbone.js',
      '../krankshaft/static/js/*.js',
      'spec/*.js'
    ],
    frameworks: ['jasmine'],
    preprocessors: {
      '../krankshaft/static/js/*.js': ['coverage']
    },
    reporters: ['progress', 'coverage'],
    singleRun: true
  });
};
