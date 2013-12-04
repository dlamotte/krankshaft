describe('krankshaft', function() {
  var schema = {
    'resources': {
      'resource': {
        url: '/api/v1/resource/',
        endpoint: {
          single: {
            url: '/api/v1/resource/:id/',
            params: [
              'id'
            ],
            allow: [
              'PUT',
              'DELETE',
              'GET'
            ]
          },
          set: {
            url: '/api/v1/resource/set/:idset/',
            params: [
              'idset'
            ],
            allow: [
              'PUT',
              'DELETE',
              'GET'
            ]
          },
          list: {
            url: '/api/v1/resource/',
            params: [ ],
            allow: [
              'POST',
              'DELETE',
              'GET'
            ]
          }
        },
        fields: {}
      },
      'nourl': {
        url: '',
        endpoint: {
          list: {
            url: ''
          }
        },
        fields: {}
      }
    }
  };

  var api;

  beforeEach(function() {
    api = new ks.make_api(schema, '', '');
  });

  describe('reverse', function() {
    it('a simple view', function() {
      expect(api.reverse('resource')).toEqual('/api/v1/resource/');
    });

    it('an endpoint with args', function() {
      expect(api.reverse('resource:single', 1)).toEqual('/api/v1/resource/1/');
      expect(api.reverse('resource:set', '1;2')).toEqual('/api/v1/resource/set/1;2/');
      expect(api.reverse('resource:list')).toEqual('/api/v1/resource/');
    });

    it('an endpoint with kwargs', function() {
      expect(api.reverse('resource:single', {id: 1})).toEqual('/api/v1/resource/1/');
      expect(api.reverse('resource:set', {idset: '1;2'})).toEqual('/api/v1/resource/set/1;2/');
      expect(api.reverse('resource:list')).toEqual('/api/v1/resource/');
    });

    it('throw when needed args not specified', function() {
      expect(function() { api.reverse('resource', 1); }).toThrow();
      expect(function() { api.reverse('resource:list', 1); }).toThrow();
      expect(function() { api.reverse('resource:set'); }).toThrow();
      expect(function() { api.reverse('resource:single'); }).toThrow();
    });

    it('throw when needed kwargs not specified', function() {
      expect(function() { api.reverse('resource', {id: 1}); }).toThrow();
      expect(function() { api.reverse('resource:list', {id: 1}); }).toThrow();
      expect(function() { api.reverse('resource:set', {key: 1}); }).toThrow();
      expect(function() { api.reverse('resource:single', {key: 1}); }).toThrow();
    });

    it('throw when no resource specified', function() {
      expect(function() { api.reverse(); }).toThrow();
    });

    it('throw when resource not found', function() {
      expect(function() { api.reverse('notaresource'); }).toThrow();
    });

    it('throw when endpoint doesnt exist', function() {
      expect(function() { api.reverse('resource:notanendpoint'); }).toThrow();
    });

    it('throw when url doesnt exist', function() {
      expect(function() { api.reverse('nourl'); }).toThrow();
      expect(function() { api.reverse('nourl:list'); }).toThrow();
    });
  });
});
